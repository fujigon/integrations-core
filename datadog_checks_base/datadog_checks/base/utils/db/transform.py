# (C) Datadog, Inc. 2019
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from __future__ import division

import re

from ... import is_affirmative
from .. import constants
from ..common import compute_percent, total_time_to_temporal_percent
from .utils import create_extra_transformer

# Used for the user-defined `expression`s
ALLOWED_GLOBALS = {
    '__builtins__': {
        # pytest turns it into a dict instead of a module
        name: getattr(__builtins__, name) if hasattr(__builtins__, name) else globals()['__builtins__'][name]
        for name in ('abs', 'all', 'any', 'bool', 'divmod', 'float', 'int', 'len', 'max', 'min', 'pow', 'str', 'sum')
    }
}

# Simple heuristic to not mistake a source for part of a string (which we also transform it into)
SOURCE_PATTERN = r'(?<!"|\')({})(?!"|\')'


def get_tag(column_name, transformers, **modifiers):
    template = '{}:{{}}'.format(column_name)
    boolean = is_affirmative(modifiers.pop('boolean', None))

    def tag(value, *_, **kwargs):
        if boolean:
            value = str(is_affirmative(value)).lower()

        return template.format(value)

    return tag


def get_monotonic_gauge(column_name, transformers, **modifiers):
    gauge = transformers['gauge']('{}.total'.format(column_name), transformers, **modifiers)
    monotonic_count = transformers['monotonic_count']('{}.count'.format(column_name), transformers, **modifiers)

    def monotonic_gauge(value, *_, **kwargs):
        gauge(value, **kwargs)
        monotonic_count(value, **kwargs)

    return monotonic_gauge


def get_temporal_percent(column_name, transformers, **modifiers):
    scale = modifiers.pop('scale', None)
    if scale is None:
        raise ValueError('the `scale` parameter is required')

    if isinstance(scale, str):
        scale = constants.TIME_UNITS.get(scale.lower())
        if scale is None:
            raise ValueError(
                'the `scale` parameter must be one of: {}'.format(' | '.join(sorted(constants.TIME_UNITS)))
            )
    elif not isinstance(scale, int):
        raise ValueError(
            'the `scale` parameter must be an integer representing parts of a second e.g. 1000 for millisecond'
        )

    rate = transformers['rate'](column_name, transformers, **modifiers)

    def temporal_percent(value, *_, **kwargs):
        rate(total_time_to_temporal_percent(value, scale=scale), **kwargs)

    return temporal_percent


def get_match(column_name, transformers, **modifiers):
    # Do work in a separate function to avoid having to `del` a bunch of variables
    compiled_items = _compile_match_items(transformers, modifiers)

    def match(value, sources, *_, **kwargs):
        if value in compiled_items:
            source, transformer = compiled_items[value]
            transformer(sources[source], **kwargs)

    return match


def get_expression(name, transformers, **modifiers):
    available_sources = modifiers.pop('sources')

    expression = modifiers.pop('expression', None)
    if expression is None:
        raise ValueError('the `expression` parameter is required')
    elif not isinstance(expression, str):
        raise ValueError('the `expression` parameter must be a string')
    elif not expression:
        raise ValueError('the `expression` parameter must not be empty')

    if not modifiers.pop('verbose', False):
        # Sort the sources in reverse order of length to prevent greedy matching
        available_sources = sorted(available_sources, key=lambda s: -len(s))

        # Escape special characters, mostly for the possible dots in metric names
        available_sources = list(map(re.escape, available_sources))

        # Finally, utilize the order by relying on the guarantees provided by the alternation operator
        available_sources = '|'.join(available_sources)

        expression = re.sub(
            SOURCE_PATTERN.format(available_sources),
            # Replace by the particular source that matched
            lambda match_obj: 'SOURCES["{}"]'.format(match_obj.group(1)),
            expression,
        )

    expression = compile(expression, filename=name, mode='eval')

    del available_sources

    if 'submit_type' in modifiers:
        if modifiers['submit_type'] not in transformers:
            raise ValueError('unknown submit_type `{}`'.format(modifiers['submit_type']))

        submit_method = transformers[modifiers.pop('submit_type')](name, transformers, **modifiers)
        submit_method = create_extra_transformer(submit_method)

        def execute_expression(sources, **kwargs):
            result = eval(expression, ALLOWED_GLOBALS, {'SOURCES': sources})
            submit_method(sources, result, **kwargs)
            return result

    else:

        def execute_expression(sources, **kwargs):
            return eval(expression, ALLOWED_GLOBALS, {'SOURCES': sources})

    return execute_expression


def get_percent(name, transformers, **modifiers):
    available_sources = modifiers.pop('sources')

    part = modifiers.pop('part', None)
    if part is None:
        raise ValueError('the `part` parameter is required')
    elif not isinstance(part, str):
        raise ValueError('the `part` parameter must be a string')
    elif part not in available_sources:
        raise ValueError('the `part` parameter `{}` is not an available source'.format(part))

    total = modifiers.pop('total', None)
    if total is None:
        raise ValueError('the `total` parameter is required')
    elif not isinstance(total, str):
        raise ValueError('the `total` parameter must be a string')
    elif total not in available_sources:
        raise ValueError('the `total` parameter `{}` is not an available source'.format(total))

    del available_sources
    gauge = transformers['gauge'](name, transformers, **modifiers)
    gauge = create_extra_transformer(gauge)

    def percent(sources, **kwargs):
        gauge(sources, compute_percent(sources[part], sources[total]), **kwargs)

    return percent


COLUMN_TRANSFORMERS = {
    'temporal_percent': get_temporal_percent,
    'monotonic_gauge': get_monotonic_gauge,
    'tag': get_tag,
    'match': get_match,
}

EXTRA_TRANSFORMERS = {'expression': get_expression, 'percent': get_percent}


def _compile_match_items(transformers, modifiers):
    items = modifiers.pop('items', None)
    if items is None:
        raise ValueError('the `items` parameter is required')

    if not isinstance(items, dict):
        raise ValueError('the `items` parameter must be a mapping')

    global_transform_source = modifiers.pop('source', None)

    compiled_items = {}
    for item, data in items.items():
        if not isinstance(data, dict):
            raise ValueError('item `{}` is not a mapping'.format(item))

        transform_name = data.pop('name', None)
        if not transform_name:
            raise ValueError('the `name` parameter for item `{}` is required'.format(item))
        elif not isinstance(transform_name, str):
            raise ValueError('the `name` parameter for item `{}` must be a string'.format(item))

        transform_type = data.pop('type', None)
        if not transform_type:
            raise ValueError('the `type` parameter for item `{}` is required'.format(item))
        elif not isinstance(transform_type, str):
            raise ValueError('the `type` parameter for item `{}` must be a string'.format(item))
        elif transform_type not in transformers:
            raise ValueError('unknown type `{}` for item `{}`'.format(transform_type, item))

        transform_source = data.pop('source', global_transform_source)
        if not transform_source:
            raise ValueError('the `source` parameter for item `{}` is required'.format(item))
        elif not isinstance(transform_source, str):
            raise ValueError('the `source` parameter for item `{}` must be a string'.format(item))

        transform_modifiers = modifiers.copy()
        transform_modifiers.update(data)
        compiled_items[item] = (
            transform_source,
            transformers[transform_type](transform_name, transformers, **transform_modifiers),
        )

    return compiled_items
