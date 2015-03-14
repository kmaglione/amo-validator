import actions

#(branches,
# explicitly_dynamic,
# estab_context,
# action,
# returns, # as in yielding a value, not breaking execution
# block_statement,
#)

def node(branches=(), dynamic=False, action=None, returns=False,
         is_block=False, complexity=1):
    return branches, dynamic, action, returns, is_block, complexity


DEFINITIONS = {
    "EmptyStatement": node(complexity=0),
    "DebuggerStatement": node(),

    "Program": node(branches=("body", ), is_block=True),
    "BlockStatement": node(branches=("body", ), is_block=True, complexity=2),
    "ExpressionStatement": node(branches=("expression", ),
                                action=actions._expression,
                                returns=True),
    "IfStatement": node(branches=("test", "alternate", "consequent"),
                        is_block=True, complexity=2),
    "LabeledStatement": node(branches=("body", ), complexity=2),
    "BreakStatement": node(complexity=2),
    "ContinueStatement": node(complexity=2),
    "WithStatement": node(branches=("body", "object"),
                          action=actions._define_with, is_block=True),
    "SwitchStatement": node(branches=("test", "cases"), is_block=True,
                            complexity=3),
    "ReturnStatement": node(branches=("argument", ), complexity=2),
    "ThrowStatement": node(branches=("argument", )),
    "TryStatement": node(branches=("block", "handler", "finalizer",
                                   "guardedHandlers"),
                         is_block=True, complexity=2),
    "WhileStatement": node(branches=("test", "body"), is_block=True,
                           complexity=2),
    "DoWhileStatement": node(branches=("test", "body"), is_block=True,
                             complexity=2),
    "ForStatement": node(branches=("init", "test", "update", "body"),
                         is_block=True, complexity=2),
    "ForInStatement": node(branches=("left", "right", "body"), is_block=True,
                           complexity=2),

    "FunctionDeclaration": node(branches=("body", ), dynamic=True,
                                action=actions._define_function,
                                is_block=True, complexity=3),
    "VariableDeclaration": node(branches=("declarations", ),
                                action=actions._define_var),

    "ThisExpression": node(action=actions._get_this, returns=True,
                           complexity=0),
    "ArrayExpression": node(branches=("elements", ),
                            action=actions._define_array, returns=True),
    "ObjectExpression": node(branches=("properties", ),
                             action=actions._define_obj, returns=True),
    "CallSiteObject": node(branches=("elements", ),
                           action=actions._define_template_strings,
                           returns=True),
    "TemplateLiteral": node(branches=("elements", ),
                            action=actions._define_template, returns=True),
    "FunctionExpression": node(branches=("body", ), dynamic=True,
                               action=actions._func_expr, returns=True,
                               is_block=True),
    "ArrowFunctionExpression": node(branches=("body", ), dynamic=True,
                                    action=actions._func_expr, returns=True,
                                    is_block=True),
    "SequenceExpression": node(branches=("expressions", ), returns=True),
    "UnaryExpression": node(branches=("argument", ),
                            action=actions._expr_unary, returns=True),
    "BinaryExpression": node(branches=("left", "right"),
                             action=actions._expr_binary, returns=True),
    "AssignmentExpression": node(branches=("left", "right"),
                                 action=actions._expr_assignment,
                                 returns=True),
    "UpdateExpression": node(branches=("argument", ), returns=True),
    "LogicalExpression": node(branches=("left", "right"), returns=True),
    "ConditionalExpression": node(branches=("test", "alternate", "consequent"),
                                  returns=True, complexity=2),
    "NewExpression": node(branches=("constructor", "arguments"),
                          action=actions._new, returns=True, complexity=0),
    "CallExpression": node(branches=("callee", "arguments"),
                           action=actions._call_expression, returns=True),
    "TaggedTemplate": node(branches=("callee", "arguments"),
                           action=actions._call_expression, returns=True),
    "MemberExpression": node(branches=("object", "property"),
                             action=actions.trace_member, returns=True),
    "YieldExpression": node(branches=("argument",), returns=True,
                            complexity=2),
    "ComprehensionExpression": node(branches=("body", "filter"), returns=True),
    "GeneratorExpression": node(branches=("body", "filter"), returns=True),

    "ObjectPattern": node(),
    "ArrayPattern": node(),

    "SwitchCase": node(branches=("test", "consequent"), complexity=2),
    "CatchClause": node(branches=("param", "guard", "body"), returns=True,
                        complexity=2),
    "ComprehensionBlock": node(branches=("left", "right"), returns=True),

    "Literal": node(action=actions._define_literal, returns=True,
                    complexity=0),
    "Identifier": node(action=actions._ident, returns=True,
                       complexity=0),
    "GraphExpression": node(),
    "GraphIndexExpression": node(),
    "UnaryOperator": node(returns=True),
    "BinaryOperator": node(returns=True),
    "LogicalOperator": node(returns=True),
    "AssignmentOperator": node(returns=True),
    "UpdateOperator": node(returns=True),
}
