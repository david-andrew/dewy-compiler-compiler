from abc import ABC, abstractmethod, ABCMeta
from typing import get_args, get_origin, Generator, Any, Literal, Union, Type as TypingType, dataclass_transform, Callable as TypingCallable
from types import UnionType
from dataclasses import dataclass, field, fields
from enum import Enum, auto
# from fractions import Fraction

from .tokenizer import Operator_t, escape_whitespace  # TODO: move into utils

import pdb


@dataclass_transform()
class AST(ABC):
    def __init_subclass__(cls: TypingType['AST'], **kwargs):
        """
        - automatically applies the dataclass decorator with repr=False to AST subclasses
        """
        super().__init_subclass__(**kwargs)

        # Apply the dataclass decorator with repr=False to the subclass
        dataclass(repr=False)(cls)

    # TODO: add property to all ASTs for function complete/locked/etc. meaning it and all children are settled
    @abstractmethod
    def __str__(self) -> str:
        """Return a string representation of the AST in a canonical dewy code format"""

    def __repr__(self) -> str:
        """
        Returns a string representation of the AST tree with correct indentation for each sub-component

        e.g.
        SomeAST(prop0=..., prop1=...)
        ├── child0=SomeSubAST(...)
        ├── child1=SomeOtherAST(...)
        │   ├── a=ThisAST(...)
        │   └── b=ThatAST(...)
        └── child2=AST2(...)
            └── something=ThisLastAST(...)

        Where all non-ast attributes of a node are printed on the same line as the node itself
        and all children are recursively indented a level and printed on their own line
        """
        return '\n'.join(self._gentree())

    def _gentree(self, prefix: str = '') -> Generator[str, None, None]:
        """
        a recursive generator helper function for __repr__

        Args:
            prefix: str - the string to prepend to each child line (root line already has prefix)
            name: str - the name of the current node in the tree
            # draw_branches: bool - whether each item should be drawn with branches or only use whitespace

        Returns:
            str: the string representation of the AST tree
        """
        # prefix components:
        space = '    '
        branch = '│   '
        # pointers:
        tee = '├── '
        last = '└── '

        attrs_str = ', '.join(f'{k}={v}' for k, v in self.__iter_members__() if not isinstance(v, AST))
        yield f'{self.__class__.__name__}({attrs_str})'
        children = tuple((k, v) for k, v in self.__iter_members__() if isinstance(v, AST))
        pointers = [tee] * (len(children) - 1) + [last]
        for (k, v), pointer in zip(children, pointers):
            extension = branch if pointer == tee else space
            gen = v._gentree(f'{prefix}{extension}')
            name = f'{k}=' if k else ''
            yield f'{prefix}{pointer}{name}{next(gen)}'     # first line gets name and pointer
            yield from gen                                  # rest of lines already have a prefix

    def __iter_members__(self) -> Generator[tuple[str, Any], 'AST', None]:
        """
        A method for getting all properties on the AST instance (including child ASTs, and non-AST properties).
        Returns a generator of tuples of the form (property_name, property_value)
        Allows replacing the current AST with a new one during iteration via .send()
        NOTE: Does not recurse into child ASTs
        """
        for key, value in self.__dict__.items():
            # any direct children are ASTs
            if isinstance(value, AST):
                replacement = yield key, value
                if replacement is not None:
                    setattr(self, key, replacement)
                    yield

            # any direct children are containers of ASTs
            elif is_ast_container(self.__class__.__annotations__.get(key)):
                if value is None:
                    continue
                if isinstance(value, list):
                    for i, item in enumerate(value):
                        replacement = yield '', item
                        if replacement is not None:
                            value[i] = replacement
                            yield
                # elif isinstance(value, some_other_container_type): ...
                else:
                    raise NotImplementedError(f'__iter_members__ over {type(value)} (from member "{key}") of {self} is not yet implemented')

            # properties that are not ASTs
            else:
                _ = yield key, value
                assert _ is None, f'ILLEGAL: attempted to replace non-AST value "{key}" during __iter_members__ for ast {self}'

    def __iter__(self) -> Generator['AST', None, None]:
        """DEPRECATED: Use __iter_asts__ instead"""
        raise DeprecationWarning(f'__iter__ is deprecated. Use __iter_asts__ instead')

    def __iter_asts__(self) -> Generator['AST', None, None]:
        """Return a generator of the direct children ASTs of the AST"""
        for _, child in self.__iter_members__():
            if isinstance(child, AST):
                yield child


    def __full_traversal_iter__(self) -> Generator['AST', 'AST', None]:
        """
        Recursive in-order traversal of all child ASTs of the current AST instance
        Has ability to replace the current AST with a new one during iteration via .send()
        """
        for _, child in (gen := self.__iter_members__()):
            if isinstance(child, AST):
                replacement = yield child
                if replacement is not None:
                    gen.send(replacement)
                    yield
                    child = replacement # allow traversal over all children of the replacement
                yield from child.__full_traversal_iter__()


    def is_settled(self) -> bool:
        """Return True if the neither the AST, nor any of its descendants, are prototypes"""
        for child in self.__iter_asts__():
            if not child.is_settled():
                return False
        return True


def is_ast_container(type_hint: TypingType | None) -> bool:
    """
    Determine if the type hint is a container of ASTs.
    e.g. list[AST], set[SomeSubclassOfAST|OtherSubclassOfAST], etc.

    Args:
        type_hint: TypingType | None - the type hint to check. If None, returns False

    Returns:
        bool: True if any of the contained types are subclasses of AST, False otherwise
    """
    if type_hint is None:
        return False

    # python callables are not containers regardless of if they take in or return ASTs
    if get_origin(type_hint) == get_origin(TypingCallable):
        return False


    # Iterate over all contained types
    args = get_args(type_hint)
    for arg in args:
        # Handle Union types (e.g., Union[B, C] or B | C)
        if get_origin(arg) is Union:
            if any(issubclass(sub_arg, AST) for sub_arg in get_args(arg) if isinstance(sub_arg, type)):
                return True
        elif isinstance(arg, UnionType):
            if any(issubclass(sub_arg, AST) for sub_arg in arg.__args__ if isinstance(sub_arg, type)):
                return True
        # Check if the argument itself is a subclass of the base class
        elif isinstance(arg, type) and issubclass(arg, AST):
            return True

    # no AST subclasses found
    return False


class PrototypeAST(AST, ABC):
    """Used to represent AST nodes that are not complete, and must be removed before the whole AST is evaluated"""

    def is_settled(self) -> bool:
        """By definition, prototypes are not settled"""
        return False


class Delimited(ABC):
    """used to track which ASTs are printed with their own delimiter so they can be juxtaposed without extra parentheses"""

class Type(AST):
    name: str
    parameters: list = field(default_factory=list)

    def __str__(self) -> str:
        if self.parameters:
            return f'{self.name}<{", ".join(map(str, self.parameters))}>'
        return self.name


# TODO: turn into a singleton...
# untyped type for when a declaration doesn't specify a type
untyped = Type('untyped')


class Undefined(AST):
    """undefined singleton"""
    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(Undefined, cls).__new__(cls)
        return cls.instance

    def __str__(self) -> str:
        return 'undefined'


# undefined shorthand, for convenience
undefined = Undefined()


class Void(AST):
    """void singleton"""
    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(Void, cls).__new__(cls)
        return cls.instance

    def __str__(self) -> str:
        return 'void'


# void shorthand, for convenience
void = Void()


# assign is just a binop?
# perhaps bring this one back since it's syntax that distinguishes it, not type checking
# class Assign(AST):
#     # TODO: allow bind to take in an unpack structure
#     target: Declare | Identifier | UnpackTarget
#     value: AST

#     def __str__(self):
#         return f'{self.target} = {self.value}'


class ListOfASTs(PrototypeAST):
    """Intermediate step for holding a list of ASTs that are probably captured by a container"""
    asts: list[AST]

    def __str__(self):
        return f'{", ".join(map(str, self.asts))}'


class PrototypeTuple(PrototypeAST):
    """
    A comma separated list of expressions (not wrapped in parentheses) e.g. 1, 2, 3
    There is no special in-memory representation of a tuple, it is literally just a const list
    """
    items: list[AST]

    def __str__(self):
        return f'{", ".join(map(str, self.items))}'


class Group(AST, Delimited):
    items: list[AST]

    def __str__(self):
        return f'({" ".join(map(str, self.items))})'


class Block(AST, Delimited):
    items: list[AST]

    def __str__(self):
        return f'{{{" ".join(map(str, self.items))}}}'


# class Number(AST):
#     val: int | float | Fraction

class Bool(AST):
    val: bool

    def __str__(self) -> str:
        return str(self.val).lower()


class Int(AST):
    val: int

    def __str__(self) -> str:
        return str(self.val)


class String(AST, Delimited):
    val: str

    def __str__(self) -> str:
        return f'"{escape_whitespace(self.val)}"'


class IString(AST, Delimited):
    parts: list[AST]

    def __str__(self):
        s = ''
        for part in self.parts:
            if isinstance(part, String):
                s += part.val
            else:
                s += f'{part}'
        return f'"{s}"'


class Flowable(AST, ABC):
    ...
    # def was_entered(self) -> bool:
    #     """Determine if the flowable branch was entered. Should reset before performing calls to flow and checking this."""
    #     raise NotImplementedError(f'flowables must implement `was_entered()`. No implementation found for {self.__class__}')

    # def reset_was_entered(self) -> None:
    #     """reset the state of was_entered, in preparation for executing branches in a flow"""
    #     raise NotImplementedError(f'flowables must implement `reset_was_entered()`. No implementation found for {self.__class__}')


class Flow(AST):
    branches: list[Flowable]

    def __str__(self):
        return ' else '.join(map(str, self.branches))


class If(Flowable):
    condition: AST
    body: AST

    def __str__(self):
        return f'if {self.condition} {self.body}'


class Loop(Flowable):
    condition: AST
    body: AST

    def __str__(self):
        return f'loop {self.condition} {self.body}'


class Default(Flowable):
    body: AST

    def __str__(self):
        return f'{self.body}'


class PrototypeFunctionLiteral(PrototypeAST):
    args: AST
    body: AST

    def __str__(self):
        if isinstance(self.args, Delimited):
            return f'{self.args} => {self.body}'
        return f'({self.args}) => {self.body}'


class PrototypePyAction(PrototypeAST):
    args: Group
    return_type: AST

    def __str__(self):
        return f'({self.args}): {self.return_type} => ...'


class Call(AST):
    f: AST
    args: None | AST = None

    def __str__(self):
        if self.args is None:
            return f'{self.f}()'
        if isinstance(self.args, Delimited):
            return f'{self.f}{self.args}'
        return f'{self.f}({self.args})'

from typing import cast
class BinOp(AST, ABC):
    left: AST
    right: AST

    def __post_init__(self):
        self.space = cast(bool, getattr(self, 'space', True))
        self.op_str = cast(str, getattr(self, 'op_str', None))
        assert isinstance(self.op_str, str), f'BinOp subclass "{self.__class__.__name__}" must define an `op_str` attribute'

    def __str__(self) -> str:
        if self.space:
            return f'{self.left} {self.op_str} {self.right}'
        return f'{self.left}{self.op_str}{self.right}'

class Assign(BinOp):
    op_str = '='
class PointsTo(BinOp):
    op_str = '->'
class BidirPointsTo(BinOp):
    op_str = '<->'
class Access(BinOp):
    op_str = '.'
    space = False
class Equal(BinOp):
    op_str = '=?'

# covered by OpChain([Not, Equal])
# class NotEqual(BinOp):
#     op_str = 'not=?'

class Less(BinOp):
    op_str = '<?'

class LessEqual(BinOp):
    op_str = '<=?'

class Greater(BinOp):
    op_str = '>?'

class GreaterEqual(BinOp):
    op_str = '>=?'

class  LeftShift(BinOp):
    op_str = '<<'

class  RightShift(BinOp):
    op_str = '>>'

class LeftRotate(BinOp):
    op_str = '<<<'

class RightRotate(BinOp):
    op_str = '>>>'

class LeftRotateCarry(BinOp):
    op_str = '<<!'

class RightRotateCarry(BinOp):
    op_str = '!>>'

class Add(BinOp):
    op_str = '+'

class Sub(BinOp):
    op_str = '-'

class Mul(BinOp):
    op_str = '*'

class Div(BinOp):
    op_str = '/'

class IDiv(BinOp):
    op_str = '÷'

class Mod(BinOp):
    op_str = '%'

class Pow(BinOp):
    op_str = '^'

class And(BinOp):
    op_str = 'and'

class Or(BinOp):
    op_str = 'or'

class Xor(BinOp):
    op_str = 'xor'

class Nand(BinOp):
    op_str = 'nand'

class Nor(BinOp):
    op_str = 'nor'

class Xnor(BinOp):
    op_str = 'xnor'

class IterIn(BinOp):
    op_str = 'in'

class MemberIn(BinOp):
    op_str = 'in?'

class UnaryPrefixOp(AST, ABC):
    operand: AST

    def __post_init__(self):
        self.space = cast(bool, getattr(self, 'space', False))
        self.op_str = cast(str, getattr(self, 'op_str', None))
        assert isinstance(self.op_str, str), f'UnaryPrefixOp subclass "{self.__class__.__name__}" must define an `op_str` attribute'

    def __str__(self) -> str:
        if self.space:
            return f'{self.op_str} {self.operand}'
        return f'{self.op_str}{self.operand}'

class Not(UnaryPrefixOp):
    op_str = 'not'
    space = True

class UnaryNeg(UnaryPrefixOp):
    op_str = '-'

class UnaryPos(UnaryPrefixOp):
    op_str = '+'

class UnaryMul(UnaryPrefixOp):
    op_str = '*'

class UnaryDiv(UnaryPrefixOp):
    op_str = '/'


class AtHandle(UnaryPrefixOp):
    op_str = '@'
    def __str__(self):
        if isinstance(self.operand, (Delimited, Identifier)):
            return f'@{self.operand}'
        return f'@({self.operand})'


class UnaryPostfixOp(AST, ABC):
    operand: AST

    def __post_init__(self):
        self.op_str = cast(str, getattr(self, 'op_str', None))
        assert isinstance(self.op_str, str), f'UnaryPostfixOp subclass "{self.__class__.__name__}" must define an `op_str` attribute'

    def __str__(self) -> str:
        return f'{self.operand}{self.op_str}'

class RollAxes(UnaryPostfixOp):
    op_str = '`'

class Suppress(UnaryPostfixOp):
    op_str = ';'


class BroadcastOp(AST):
    op: BinOp

    def __str__(self):
        return f'{self.op.left} .{self.op.op_str} {self.op.right}'

class BareRange(PrototypeAST):
    left: AST
    right: AST

    def __str__(self) -> str:
        return f'{self.left}..{self.right}'


class Ellipsis(AST):
    def __str__(self) -> str:
        return '...'


class Spread(AST):
    right: AST

    def __str__(self) -> str:
        return f'...{self.right}'


class Range(AST):
    left: AST
    right: AST
    brackets: Literal['[]', '[)', '(]', '()']

    def __str__(self) -> str:
        return f'{self.brackets[0]}{self.left}..{self.right}{self.brackets[1]}'


class Array(AST, Delimited):
    items: list[AST] # list[T] where T is not Declare or Assign or PointsTo or BidirPointsTo

    def __str__(self):
        return f'[{" ".join(map(str, self.items))}]'


class Dict(AST, Delimited):
    items: list[PointsTo]

    def __str__(self):
        return f'[{" ".join(map(str, self.items))}]'


class BidirDict(AST, Delimited):
    items: list[BidirPointsTo]

    def __str__(self):
        return f'[{" ".join(map(str, self.items))}]'


class ObjectLiteral(AST, Delimited):
    items: list[AST] # list[Declare|Assign|AST] has to have at least 1 declare or assignment

    def __str__(self):
        return f'[{" ".join(map(str, self.items))}]'


class TypeParam(AST, Delimited):
    items: list[AST]

    def __str__(self):
        return f'<{" ".join(map(str, self.items))}>'


class DeclareGeneric(AST):
    left: TypeParam
    right: AST

    def __str__(self):
        return f'{self.left}{self.right}'


class Parameterize(AST):
    left: AST
    right: TypeParam

    def __str__(self):
        return f'{self.left}{self.right}'


#TODO: maybe this should just be a binop, i.e. does right need to be restricted to Range|Array?
# perhaps keep since to parse an index, the right must be a Range|Array
class Index(AST):
    left: AST
    right: Range | Array

    def __str__(self):
        return f'{self.left}{self.right}'


class PrototypeIdentifier(PrototypeAST):
    name: str
    def __str__(self) -> str:
        return f'{self.name}'

class Identifier(AST):
    name: str
    def __str__(self) -> str:
        return f'{self.name}'


class Express(AST):
    id: Identifier

    def __str__(self) -> str:
        return f'{self.id}'

class TypedIdentifier(AST):
    id: Identifier
    type: AST

    def __str__(self) -> str:
        return f'{self.id}:{self.type}'


class ReturnTyped(BinOp):
    op_str = ':>'

class UnpackTarget(AST):
    target: 'list[Identifier | TypedIdentifier | UnpackTarget | Assign | Spread]'
    def __str__(self) -> str:
        return f'[{" ".join(map(str, self.target))}]'

class DeclarationType(Enum):
    LET = auto()
    CONST = auto()
    # LOCAL_CONST = auto()
    # FIXED_TYPE = auto()

    # default for binding without declaring
    # DEFAULT = LET


class Declare(AST):
    decltype: DeclarationType
    target: Identifier | TypedIdentifier | ReturnTyped | UnpackTarget | Assign

    def __str__(self):
        return f'{self.decltype.name.lower()} {self.target}'



if __name__ == '__main__':
    # DEBUG testing tree string printing
    class _Add(AST):
        l: AST
        r: AST

        def __str__(self) -> str:
            return f'{self.l} + {self.r}'

    class _Mul(AST):
        l: AST
        r: AST

        def __str__(self) -> str:
            return f'{self.l} * {self.r}'

    class _List(AST):
        items: list[AST]

        def __str__(self) -> str:
            return f'[{", ".join(map(str, self.items))}]'

    class _Int(AST):
        value: int

        def __str__(self) -> str:
            return str(self.value)

    # big long test ast
    test = _Add(
        _Add(
            _Int(1),
            _List([_Int(2), _Int(3), _Int(4), _Int(5)])
        ),
        _Mul(
            _Int(2),
            _Add(
                _Mul(
                    _Int(3),
                    _Int(4)
                ),
                _Mul(
                    _Int(5),
                    _Int(6)
                )
            )
        )
    )

    print(repr(test))
    print(str(test))
    # class Broken(AST):
    #     num: int
    #     def __str__(self) -> str:
    #         return f'{self.num}'
    #     def __iter__(self) -> Generator['AST', None, None]:
    #         yield Int(self.num)
