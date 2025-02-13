# (C) Datadog, Inc. 2019
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from copy import deepcopy

from six import raise_from

from .utils import create_extra_transformer


class Query(object):
    def __init__(self, query_data):
        self.query_data = deepcopy(query_data or {})
        self.name = None
        self.query = None
        self.columns = None
        self.extras = None
        self.tags = None

    def compile(self, column_transformers, extra_transformers):
        # Check for previous compilation
        if self.name is not None:
            return

        query_name = self.query_data.get('name')
        if not query_name:
            raise ValueError('query field `name` is required')
        elif not isinstance(query_name, str):
            raise ValueError('query field `name` must be a string')

        query = self.query_data.get('query')
        if not query:
            raise ValueError('field `query` for {} is required'.format(query_name))
        elif not isinstance(query, str):
            raise ValueError('field `query` for {} must be a string'.format(query_name))

        columns = self.query_data.get('columns')
        if not columns:
            raise ValueError('field `columns` for {} is required'.format(query_name))
        elif not isinstance(columns, list):
            raise ValueError('field `columns` for {} must be a list'.format(query_name))

        tags = self.query_data.get('tags', [])
        if tags is not None and not isinstance(tags, list):
            raise ValueError('field `tags` for {} must be a list'.format(query_name))

        # Keep track of all defined names
        sources = {}

        column_data = []
        for i, column in enumerate(columns, 1):
            # Columns can be ignored via configuration.
            if not column:
                column_data.append((None, None))
                continue
            elif not isinstance(column, dict):
                raise ValueError('column #{} of {} is not a mapping'.format(i, query_name))

            column_name = column.get('name')
            if not column_name:
                raise ValueError('field `name` for column #{} of {} is required'.format(i, query_name))
            elif not isinstance(column_name, str):
                raise ValueError('field `name` for column #{} of {} must be a string'.format(i, query_name))
            elif column_name in sources:
                raise ValueError(
                    'the name {} of {} was already defined in {} #{}'.format(
                        column_name, query_name, sources[column_name]['type'], sources[column_name]['index']
                    )
                )

            sources[column_name] = {'type': 'column', 'index': i}

            column_type = column.get('type')
            if not column_type:
                raise ValueError('field `type` for column {} of {} is required'.format(column_name, query_name))
            elif not isinstance(column_type, str):
                raise ValueError('field `type` for column {} of {} must be a string'.format(column_name, query_name))
            elif column_type == 'source':
                column_data.append((column_name, (None, None)))
                continue
            elif column_type not in column_transformers:
                raise ValueError('unknown type `{}` for column {} of {}'.format(column_type, column_name, query_name))

            modifiers = {key: value for key, value in column.items() if key not in ('name', 'type')}

            try:
                transformer = column_transformers[column_type](column_name, column_transformers, **modifiers)
            except Exception as e:
                error = 'error compiling type `{}` for column {} of {}: {}'.format(
                    column_type, column_name, query_name, e
                )

                # Prepend helpful error text.
                #
                # When an exception is raised in the context of another one, both will be printed. To avoid
                # this we set the context to None. https://www.python.org/dev/peps/pep-0409/
                raise_from(type(e)(error), None)
            else:
                if column_type == 'tag':
                    column_data.append((column_name, (column_type, transformer)))
                else:
                    # All these would actually submit data. As that is the default case, we represent it as
                    # a reference to None since if we use e.g. `value` it would never be checked anyway.
                    column_data.append((column_name, (None, transformer)))

        submission_transformers = column_transformers.copy()
        submission_transformers.pop('tag')

        extras = self.query_data.get('extras', [])
        if not isinstance(extras, list):
            raise ValueError('field `extras` for {} must be a list'.format(query_name))

        extra_data = []
        for i, extra in enumerate(extras, 1):
            if not isinstance(extra, dict):
                raise ValueError('extra #{} of {} is not a mapping'.format(i, query_name))

            extra_name = extra.get('name')
            if not extra_name:
                raise ValueError('field `name` for extra #{} of {} is required'.format(i, query_name))
            elif not isinstance(extra_name, str):
                raise ValueError('field `name` for extra #{} of {} must be a string'.format(i, query_name))
            elif extra_name in sources:
                raise ValueError(
                    'the name {} of {} was already defined in {} #{}'.format(
                        extra_name, query_name, sources[extra_name]['type'], sources[extra_name]['index']
                    )
                )

            sources[extra_name] = {'type': 'extra', 'index': i}

            extra_type = extra.get('type')
            if not extra_type:
                if 'expression' in extra:
                    extra_type = 'expression'
                else:
                    raise ValueError('field `type` for extra {} of {} is required'.format(extra_name, query_name))
            elif not isinstance(extra_type, str):
                raise ValueError('field `type` for extra {} of {} must be a string'.format(extra_name, query_name))
            elif extra_type not in extra_transformers and extra_type not in submission_transformers:
                raise ValueError('unknown type `{}` for extra {} of {}'.format(extra_type, extra_name, query_name))

            transformer_factory = extra_transformers.get(extra_type, submission_transformers.get(extra_type))

            extra_source = extra.get('source')
            if extra_type in submission_transformers:
                if not extra_source:
                    raise ValueError('field `source` for extra {} of {} is required'.format(extra_name, query_name))

                modifiers = {key: value for key, value in extra.items() if key not in ('name', 'type', 'source')}
            else:
                modifiers = {key: value for key, value in extra.items() if key not in ('name', 'type')}
                modifiers['sources'] = sources

            try:
                transformer = transformer_factory(extra_name, submission_transformers, **modifiers)
            except Exception as e:
                error = 'error compiling type `{}` for extra {} of {}: {}'.format(extra_type, extra_name, query_name, e)

                raise_from(type(e)(error), None)
            else:
                if extra_type in submission_transformers:
                    transformer = create_extra_transformer(transformer, extra_source)

                extra_data.append((extra_name, transformer))

        self.name = query_name
        self.query = query
        self.columns = tuple(column_data)
        self.extras = tuple(extra_data)
        self.tags = tags
        del self.query_data
