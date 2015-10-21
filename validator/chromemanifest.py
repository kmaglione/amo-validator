import os.path
import re

from validator.contextgenerator import ContextGenerator


class ChromeManifest(object):
    """This class enables convenient parsing and iteration of
    chrome.manifest files."""

    def __init__(self, xpi, path, err=None):
        self.xpi = xpi
        self.err = err

        self.manifests = set()

        self.entries = list(self.read_manifest(path))

    def read_manifest(self, path, from_entry=None):
        """Read the manifest at the given path, yielding every entry in that
        file, and any sub-manifests."""

        if path in self.manifests:
            return

        path = self.normalize(path)

        self.manifests.add(path)

        try:
            data = self.xpi.read(path)
        except Exception:
            if from_entry:
                self.err.notice(
                    err_id=('submain', 'populate_chrome_manifest', 'linkerr'),
                    notice='Linked manifest could not be found.',
                    description=('A linked manifest file could not be found '
                                 'in the package.',
                                 'Path: %s' % path),
                    filename=from_entry['filename'],
                    line=from_entry['line'],
                    context=from_entry['context'])
            return

        context = ContextGenerator(data)

        lines = data.split('\n')

        for line_no, line in enumerate(lines):
            line = re.sub('#.*', '', line).strip()

            line = line.split()
            if len(line) < 2:
                continue
            if len(line) < 3:
                line.append('')

            type_ = line.pop(0)

            entry = {'type': type_,
                     'args': tuple(line),
                     'line': line_no + 1,
                     'filename': path,
                     'context': context}

            if type_ == 'manifest':
                path_ = self.resolve(entry, line[0])
                for entry in self.read_manifest(path_, entry):
                    yield entry
            else:
                yield entry

    def normalize(self, path):
        """Normalize a path."""

        path = re.sub(r'//+', '/', path)
        path = path.lstrip('/')

        return path

    def resolve(self, entry, path):
        """Resolve the given path relative to its manifest file."""

        base_path = os.path.dirname(entry['filename'])

        return os.path.join(base_path, path)

    def get_entries(self, type_=None, *args):
        """Returns entries matching the specified type and args."""

        assert type_ is not None or not args

        for entry in self.entries:
            if type_ is not None and entry['type'] != type_:
                continue

            if entry['args'][:len(args)] != args:
                continue

            yield entry

    def is_component(self, path):
        """Return true if the file at the given path is a component."""

        path = self.normalize(path)

        for entry in self.get_entries('component'):
            path_ = self.resolve(entry, entry['args'][1])

            if path == path_:
                return True

        return False

    def get_applicable_overlays(self, error_bundle):
        """
        Given an error bundle, a list of overlays that are present in the
        current package or subpackage are returned.
        """

        content_paths = self.get_entries('content')
        if not content_paths:
            return set()

        # Create some variables that will store where the applicable content
        # instruction path references and where it links to.
        chrome_path = ''
        content_root_path = '/'

        # Look through each of the listed packages and paths.
        for path in content_paths:
            chrome_name = path['args'][0]
            path_location = path['args'][1]

            # Handle jarred paths differently.
            if path_location.startswith('jar:'):
                if not error_bundle.is_nested_package:
                    continue

                # Parse out the JAR and it's location within the chrome.
                split_jar_url = path_location[4:].split('!', 2)
                # Ignore invalid/unsupported JAR URLs.
                if len(split_jar_url) != 2:
                    continue

                # Unpack the JAR URL.
                jar_path, package_path = split_jar_url

                # Ignore the instruction if the JAR it points to doesn't match
                # up with the current subpackage tree.
                if jar_path != error_bundle.package_stack[0]:
                    continue
                chrome_path = self._url_chunk_join(chrome_name, package_path)
                # content_root_path stays at the default: /

                break
            else:
                # If we're in a subpackage, a content instruction referring to
                # the root of the package obviously doesn't apply.
                if error_bundle.is_nested_package:
                    continue

                chrome_path = self._url_chunk_join(chrome_name, 'content')
                content_root_path = '/%s/' % path_location.strip('/')
                break

        if not chrome_path:
            return set()

        applicable_overlays = set()
        chrome_path = 'chrome://%s' % self._url_chunk_join(chrome_path + '/')

        for overlay in self.get_entries('overlay'):
            if not overlay['args'][1]:
                error_bundle.error(
                    err_id=('chromemanifest', 'get_applicable_overalys',
                            'object'),
                    error='Overlay instruction missing a property.',
                    description='When overlays are registered in a chrome '
                                'manifest file, they require a namespace and '
                                'a chrome URL at minimum.',
                    filename=overlay['filename'],
                    line=overlay['line'],
                    context=overlay['context'])
                continue
            overlay_url = overlay['args'][1]
            if overlay_url.startswith(chrome_path):
                overlay_relative_path = overlay_url[len(chrome_path):]
                applicable_overlays.add('/%s' % self._url_chunk_join(
                    content_root_path, overlay_relative_path))

        return applicable_overlays

    def reverse_lookup(self, state, path):
        """
        Returns a chrome URL for a given path, given the current package depth
        in an error bundle.

        State may either be an error bundle or the actual package stack.
        """

        # Make sure the path starts with a forward slash.
        if not path.startswith('/'):
            path = '/%s' % path

        # If the state is an error bundle, extract the package stack.
        if not isinstance(state, list):
            state = state.package_stack

        content_paths = self.get_entries('content')
        for content_path in content_paths:
            chrome_name = content_path['args'][0]
            path_location = content_path['args'][1]

            if path_location.startswith('jar:'):
                if not state:
                    continue

                # Parse out the JAR and it's location within the chrome.
                split_jar_url = path_location[4:].split('!', 2)
                # Ignore invalid/unsupported JAR URLs.
                if len(split_jar_url) != 2:
                    continue

                # Unpack the JAR URL.
                jar_path, package_path = split_jar_url

                if jar_path != state[0]:
                    continue

                return 'chrome://%s' % self._url_chunk_join(chrome_name,
                                                            package_path,
                                                            path)
            else:
                if state:
                    continue

                path_location = '/%s/' % path_location.strip('/')
                rel_path = os.path.relpath(path, path_location)

                if rel_path.startswith('../') or rel_path == '..':
                    continue

                return 'chrome://%s' % self._url_chunk_join(chrome_name,
                                                            rel_path)

        return None

    def _url_chunk_join(self, *args):
        """Join the arguments together to form a predictable URL chunk."""
        # Strip slashes from either side of each path piece.
        pathlets = map(lambda s: s.strip('/'), args)
        # Remove empty pieces.
        pathlets = filter(None, pathlets)
        url = '/'.join(pathlets)
        # If this is a directory, add a trailing slash.
        if args[-1].endswith('/'):
            url = '%s/' % url
        return url
