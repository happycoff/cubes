
# -*- coding=utf -*-

from collections import namedtuple
from ...errors import *

try:
    import sqlalchemy
    import sqlalchemy.sql as sql
    from sqlalchemy.sql.functions import ReturnTypeFromArgs
except ImportError:
    from cubes.common import MissingPackage
    sqlalchemy = sql = MissingPackage("sqlalchemy", "SQL aggregation browser")
    missing_error = MissingPackage("sqlalchemy", "SQL browser extensions")

    class ReturnTypeFromArgs(object):
        def __init__(*args, **kwargs):
            # Just fail by trying to call missing package
            missing_error()


__all__ = (
    "get_aggregate_function",
    "available_aggregate_functions"
)


class AggregateFunction(object):
    requires_measure = True

    # if `True` then on `coalesce` the values are coalesced to 0 before the
    # aggregation. If `False` then the values are as they are and the result is
    # coalesced to 0.
    coalesce_values = True

    def __init__(self, name_, function_=None, *args, **kwargs):
        self.name = name_
        self.function = function_
        self.args = args
        self.kwargs = kwargs

    def __call__(self, aggregate, context, coalesce=False):
        """Applied the function on the aggregate and returns labelled
        expression. SQL expression label is the aggregate's name. This method
        calls `apply()` method which can be overriden by subclasses."""

        expression = self.apply(aggregate, context, coalesce)
        expression = expression.label(aggregate.name)
        return expression

    def coalesce_value(self, aggregate, value):
        """Coalesce the value before aggregation of `aggregate`. `value` is a
        SQLAlchemy expression. Default implementation does nothing, just
        returns the `value`."""
        return value

    def coalesce_aggregate(self, aggregate, value):
        """Coalesce the aggregated value of `aggregate`. `value` is a
        SQLAlchemy expression. Default implementation does nothing, just
        returns the `value`."""
        return value

    def apply(self, aggregate, context=None, coalesce=False):
        """Apply the function on the aggregate. Subclasses might override this
        method and use other `aggregates` and browser context.

        If `missing_value` is not `None`, then the aggregate's source value
        should be wrapped in ``COALESCE(column, missing_value)``.

        Returns a SQLAlchemy expression."""

        if not context:
            raise InternalError("No context provided for AggregationFunction")

        if not aggregate.measure:
            raise ModelError("No measure specified for aggregate %s, "
                             "required for aggregate function %s"
                             % (str(aggregate), self.name))

        measure = context.cube.measure(aggregate.measure)
        column = context.column(measure)

        if coalesce:
            column = self.coalesce_value(aggregate, column)

        expression = self.function(column, *self.args, **self.kwargs)

        if coalesce:
            column = self.coalesce_aggregate(aggregate, expression)

        return expression

    def __str__(self):
        return self.name

class ValueCoalescingFunction(AggregateFunction):
    def coalesce_value(self, aggregate, value):
        """Coalesce the value before aggregation of `aggregate`. `value` is a
        SQLAlchemy expression.  Default implementation coalesces to zero 0."""
        # TODO: use measure's missing value (we need to get the measure object
        # somehow)
        return sql.functions.coalesce(value, 0)

class SummaryCoalescingFunction(AggregateFunction):
    def coalesce_aggregate(self, aggregate, value):
        """Coalesce the aggregated value of `aggregate`. `value` is a
        SQLAlchemy expression.  Default implementation does nothing."""
        # TODO: use aggregates's missing value
        return sql.functions.coalesce(value, 0)

class GenerativeFunction(AggregateFunction):
    def __init__(self, name, function=None, *args, **kwargs):
        """Creates a function that generates a value without using any of the
        measures."""
        super(GenerativeFunction, self).__init__(name, function)

    def apply(self, aggregate, context=None, missing_value=None):
        return self.function(*self.args, **self.kwargs)


class avg(ReturnTypeFromArgs):
    pass


# Works with PostgreSQL
class stddev(ReturnTypeFromArgs):
    pass


class variance(ReturnTypeFromArgs):
    pass


_functions = (
    SummaryCoalescingFunction("sum", sql.functions.sum),
    SummaryCoalescingFunction("count_nonempty", sql.functions.count),
    ValueCoalescingFunction("min", sql.functions.min),
    ValueCoalescingFunction("max", sql.functions.max),
    ValueCoalescingFunction("avg", avg),
    ValueCoalescingFunction("stddev", stddev),
    ValueCoalescingFunction("variance", variance),
    ValueCoalescingFunction("identity", lambda c: c),

    GenerativeFunction("count", sql.functions.count, 1),
)

_function_dict = {}


def _create_function_dict():
    if not _function_dict:
        for func in _functions:
            _function_dict[func.name] = func


def get_aggregate_function(name):
    """Returns an aggregate function `name`. The returned function takes two
    arguments: `aggregate` and `context`. When called returns a labelled
    SQL expression."""

    _create_function_dict()
    return _function_dict[name]


def available_aggregate_functions():
    """Returns a list of available aggregate function names."""
    _create_function_dict()
    return _function_dict.keys()

