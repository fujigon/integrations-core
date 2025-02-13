# (C) Datadog, Inc. 2019
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from .utils import default_option_example, normalize_source_name


def spec_validator(spec, loader):
    if not isinstance(spec, dict):
        loader.errors.append('{}: Configuration specifications must be a mapping object'.format(loader.source))
        return

    if 'name' not in spec:
        loader.errors.append(
            '{}: Configuration specifications must contain a top-level `name` attribute'.format(loader.source)
        )
        return

    name = spec['name']
    if not isinstance(name, str):
        loader.errors.append('{}: The top-level `name` attribute must be a string'.format(loader.source))
        return

    release_version = spec.setdefault('version', loader.version)
    if not release_version:
        loader.errors.append(
            '{}: Configuration specifications must contain a top-level `version` attribute'.format(loader.source)
        )
        return
    elif not isinstance(release_version, str):
        loader.errors.append('{}: The top-level `version` attribute must be a string'.format(loader.source))
        return

    if 'files' not in spec:
        loader.errors.append(
            '{}: Configuration specifications must contain a top-level `files` attribute'.format(loader.source)
        )
        return

    files = spec['files']
    if not isinstance(files, list):
        loader.errors.append('{}: The top-level `files` attribute must be an array'.format(loader.source))
        return

    files_validator(files, loader)


def files_validator(files, loader):
    num_files = len(files)
    file_names_origin = {}
    example_file_names_origin = {}
    for file_index, config_file in enumerate(files, 1):
        if not isinstance(config_file, dict):
            loader.errors.append(
                '{}, file #{}: File attribute must be a mapping object'.format(loader.source, file_index)
            )
            continue

        if 'name' not in config_file:
            loader.errors.append(
                '{}, file #{}: Every file must contain a `name` attribute representing the '
                'final destination the Agent loads'.format(loader.source, file_index)
            )
            continue

        file_name = config_file['name']
        if not isinstance(file_name, str):
            loader.errors.append('{}, file #{}: Attribute `name` must be a string'.format(loader.source, file_index))
            continue

        if file_name in file_names_origin:
            loader.errors.append(
                '{}, file #{}: File name `{}` already used by file #{}'.format(
                    loader.source, file_index, file_name, file_names_origin[file_name]
                )
            )
        else:
            file_names_origin[file_name] = file_index

        if file_name == 'auto_conf.yaml':
            if 'example_name' in config_file and config_file['example_name'] != file_name:
                loader.errors.append(
                    '{}, file #{}: Example file name `{}` should be `{}`'.format(
                        loader.source, file_index, config_file['example_name'], file_name
                    )
                )

            example_file_name = config_file.setdefault('example_name', file_name)
        else:
            if num_files == 1:
                expected_name = '{}.yaml'.format(normalize_source_name(loader.source or 'conf'))
                if file_name != expected_name:
                    loader.errors.append(
                        '{}, file #{}: File name `{}` should be `{}`'.format(
                            loader.source, file_index, file_name, expected_name
                        )
                    )

            example_file_name = config_file.setdefault('example_name', 'conf.yaml.example')

        if not isinstance(example_file_name, str):
            loader.errors.append(
                '{}, file #{}: Attribute `example_name` must be a string'.format(loader.source, file_index)
            )

        if example_file_name in example_file_names_origin:
            loader.errors.append(
                '{}, file #{}: Example file name `{}` already used by file #{}'.format(
                    loader.source, file_index, example_file_name, example_file_names_origin[example_file_name]
                )
            )
        else:
            example_file_names_origin[example_file_name] = file_index

        if 'options' not in config_file:
            loader.errors.append(
                '{}, {}: Every file must contain an `options` attribute'.format(loader.source, file_name)
            )
            continue

        options = config_file['options']
        if not isinstance(options, list):
            loader.errors.append('{}, {}: The `options` attribute must be an array'.format(loader.source, file_name))
            continue

        options_validator(options, loader, file_name)


def options_validator(options, loader, file_name, *sections):
    sections_display = ', '.join(sections)
    if sections_display:
        sections_display += ', '

    option_names_origin = {}
    for option_index, option in enumerate(options, 1):
        if not isinstance(option, dict):
            loader.errors.append(
                '{}, {}, {}option #{}: Option attribute must be a mapping object'.format(
                    loader.source, file_name, sections_display, option_index
                )
            )
            continue

        if 'template' in option:
            parameters = {
                parameter: option.pop(parameter) for parameter in loader.templates.fields if parameter in option
            }

            try:
                template = loader.templates.load(option.pop('template'), parameters)
            except Exception as e:
                loader.errors.append(
                    '{}, {}, {}option #{}: {}'.format(loader.source, file_name, sections_display, option_index, e)
                )
                continue

            if isinstance(template, dict):
                template.update(option)
                option = template
                options[option_index - 1] = template
            elif isinstance(template, list):
                if template:
                    option = template[0]
                    for item_index, template_item in enumerate(template):
                        options.insert(option_index + item_index, template_item)

                    # Delete what's at the current index
                    options.pop(option_index - 1)

                    # Perform this check once again
                    if not isinstance(option, dict):
                        loader.errors.append(
                            '{}, {}, {}option #{}: Template option must be a mapping object'.format(
                                loader.source, file_name, sections_display, option_index
                            )
                        )
                        continue
                else:
                    loader.errors.append(
                        '{}, {}, {}option #{}: Template refers to an empty array'.format(
                            loader.source, file_name, sections_display, option_index
                        )
                    )
                    continue
            else:
                loader.errors.append(
                    '{}, {}, {}option #{}: Template does not refer to a mapping object nor array'.format(
                        loader.source, file_name, sections_display, option_index
                    )
                )
                continue

        if 'name' not in option:
            loader.errors.append(
                '{}, {}, {}option #{}: Every option must contain a `name` attribute'.format(
                    loader.source, file_name, sections_display, option_index
                )
            )
            continue

        option_name = option['name']
        if not isinstance(option_name, str):
            loader.errors.append(
                '{}, {}, {}option #{}: Attribute `name` must be a string'.format(
                    loader.source, file_name, sections_display, option_index
                )
            )

        if option_name in option_names_origin:
            loader.errors.append(
                '{}, {}, {}option #{}: Option name `{}` already used by option #{}'.format(
                    loader.source,
                    file_name,
                    sections_display,
                    option_index,
                    option_name,
                    option_names_origin[option_name],
                )
            )
        else:
            option_names_origin[option_name] = option_index

        if 'description' not in option:
            loader.errors.append(
                '{}, {}, {}{}: Every option must contain a `description` attribute'.format(
                    loader.source, file_name, sections_display, option_name
                )
            )
            continue

        description = option['description']
        if not isinstance(description, str):
            loader.errors.append(
                '{}, {}, {}{}: Attribute `description` must be a string'.format(
                    loader.source, file_name, sections_display, option_name, description
                )
            )

        option.setdefault('required', False)
        if not isinstance(option['required'], bool):
            loader.errors.append(
                '{}, {}, {}{}: Attribute `required` must be true or false'.format(
                    loader.source, file_name, sections_display, option_name
                )
            )

        option.setdefault('hidden', False)
        if not isinstance(option['hidden'], bool):
            loader.errors.append(
                '{}, {}, {}{}: Attribute `hidden` must be true or false'.format(
                    loader.source, file_name, sections_display, option_name
                )
            )

        option.setdefault('deprecation', {})
        if not isinstance(option['deprecation'], dict):
            loader.errors.append(
                '{}, {}, {}{}: Attribute `deprecation` must be a mapping object'.format(
                    loader.source, file_name, sections_display, option_name
                )
            )
        else:
            for key, info in option['deprecation'].items():
                if not isinstance(info, str):
                    loader.errors.append(
                        '{}, {}, {}{}: Key `{}` for attribute `deprecation` must be a string'.format(
                            loader.source, file_name, sections_display, option_name, key
                        )
                    )

        option.setdefault('metadata_tags', [])
        if not isinstance(option['metadata_tags'], list):
            loader.errors.append(
                '{}, {}, {}{}: Attribute `metadata_tags` must be an array'.format(
                    loader.source, file_name, sections_display, option_name
                )
            )
        else:
            for metadata_tag in option['metadata_tags']:
                if not isinstance(metadata_tag, str):
                    loader.errors.append(
                        '{}, {}, {}{}: Attribute `metadata_tags` must only contain strings'.format(
                            loader.source, file_name, sections_display, option_name
                        )
                    )

        if 'value' in option and 'options' in option:
            loader.errors.append(
                '{}, {}, {}{}: An option cannot contain both `value` and `options` attributes'.format(
                    loader.source, file_name, sections_display, option_name
                )
            )
            continue

        if 'value' in option:
            value = option['value']
            if not isinstance(value, dict):
                loader.errors.append(
                    '{}, {}, {}{}: Attribute `value` must be a mapping object'.format(
                        loader.source, file_name, sections_display, option_name
                    )
                )
                continue

            option.setdefault('secret', False)
            if not isinstance(option['secret'], bool):
                loader.errors.append(
                    '{}, {}, {}{}: Attribute `secret` must be true or false'.format(
                        loader.source, file_name, sections_display, option_name
                    )
                )

            value_validator(value, loader, file_name, sections_display, option_name, depth=0)
        elif 'options' in option:
            nested_options = option['options']
            if not isinstance(nested_options, list):
                loader.errors.append(
                    '{}, {}, {}{}: The `options` attribute must be an array'.format(
                        loader.source, file_name, sections_display, option_name
                    )
                )
                continue

            option.setdefault('multiple', False)
            if not isinstance(option['multiple'], bool):
                loader.errors.append(
                    '{}, {}, {}{}: Attribute `multiple` must be true or false'.format(
                        loader.source, file_name, sections_display, option_name
                    )
                )

            previous_sections = list(sections)
            previous_sections.append(option_name)
            options_validator(nested_options, loader, file_name, *previous_sections)


def value_validator(value, loader, file_name, sections_display, option_name, depth=0):
    if 'type' not in value:
        loader.errors.append(
            '{}, {}, {}{}: Every value must contain a `type` attribute'.format(
                loader.source, file_name, sections_display, option_name
            )
        )
        return

    value_type = value['type']
    if not isinstance(value_type, str):
        loader.errors.append(
            '{}, {}, {}{}: Attribute `type` must be a string'.format(
                loader.source, file_name, sections_display, option_name
            )
        )
        return

    if value_type == 'string':
        if 'example' not in value:
            if not depth:
                value['example'] = default_option_example(option_name)
        elif not isinstance(value['example'], str):
            loader.errors.append(
                '{}, {}, {}{}: Attribute `example` for `type` {} must be a string'.format(
                    loader.source, file_name, sections_display, option_name, value_type
                )
            )

        if 'pattern' in value and not isinstance(value['pattern'], str):
            loader.errors.append(
                '{}, {}, {}{}: Attribute `pattern` for `type` {} must be a string'.format(
                    loader.source, file_name, sections_display, option_name, value_type
                )
            )
    elif value_type in ('integer', 'number'):
        if 'example' not in value:
            if not depth:
                value['example'] = default_option_example(option_name)
        elif not isinstance(value['example'], (int, float)):
            loader.errors.append(
                '{}, {}, {}{}: Attribute `example` for `type` {} must be a number'.format(
                    loader.source, file_name, sections_display, option_name, value_type
                )
            )

        minimum_valid = True
        maximum_valid = True

        if 'minimum' in value and not isinstance(value['minimum'], (int, float)):
            loader.errors.append(
                '{}, {}, {}{}: Attribute `minimum` for `type` {} must be a number'.format(
                    loader.source, file_name, sections_display, option_name, value_type
                )
            )
            minimum_valid = False

        if 'maximum' in value and not isinstance(value['maximum'], (int, float)):
            loader.errors.append(
                '{}, {}, {}{}: Attribute `maximum` for `type` {} must be a number'.format(
                    loader.source, file_name, sections_display, option_name, value_type
                )
            )
            maximum_valid = False

        if (
            'minimum' in value
            and 'maximum' in value
            and minimum_valid
            and maximum_valid
            and value['maximum'] <= value['minimum']
        ):
            loader.errors.append(
                '{}, {}, {}{}: Attribute `maximum` for `type` {} must be greater than attribute `minimum`'.format(
                    loader.source, file_name, sections_display, option_name, value_type
                )
            )
    elif value_type == 'boolean':
        if 'example' not in value:
            if not depth:
                loader.errors.append(
                    '{}, {}, {}{}: Every {} must contain a default `example` attribute'.format(
                        loader.source, file_name, sections_display, option_name, value_type
                    )
                )
        elif not isinstance(value['example'], bool):
            loader.errors.append(
                '{}, {}, {}{}: Attribute `example` for `type` {} must be true or false'.format(
                    loader.source, file_name, sections_display, option_name, value_type
                )
            )
    elif value_type == 'array':
        if 'example' not in value:
            if not depth:
                value['example'] = []
        elif not isinstance(value['example'], list):
            loader.errors.append(
                '{}, {}, {}{}: Attribute `example` for `type` {} must be an array'.format(
                    loader.source, file_name, sections_display, option_name, value_type
                )
            )

        if 'uniqueItems' in value and not isinstance(value['uniqueItems'], bool):
            loader.errors.append(
                '{}, {}, {}{}: Attribute `uniqueItems` for `type` {} must be true or false'.format(
                    loader.source, file_name, sections_display, option_name, value_type
                )
            )

        min_items_valid = True
        max_items_valid = True

        if 'minItems' in value and not isinstance(value['minItems'], int):
            loader.errors.append(
                '{}, {}, {}{}: Attribute `minItems` for `type` {} must be an integer'.format(
                    loader.source, file_name, sections_display, option_name, value_type
                )
            )
            min_items_valid = False

        if 'maxItems' in value and not isinstance(value['maxItems'], int):
            loader.errors.append(
                '{}, {}, {}{}: Attribute `maxItems` for `type` {} must be an integer'.format(
                    loader.source, file_name, sections_display, option_name, value_type
                )
            )
            max_items_valid = False

        if (
            'minItems' in value
            and 'maxItems' in value
            and min_items_valid
            and max_items_valid
            and value['maxItems'] <= value['minItems']
        ):
            loader.errors.append(
                '{}, {}, {}{}: Attribute `maxItems` for `type` {} must be greater than attribute `minItems`'.format(
                    loader.source, file_name, sections_display, option_name, value_type
                )
            )

        if 'items' not in value:
            loader.errors.append(
                '{}, {}, {}{}: Every {} must contain an `items` attribute'.format(
                    loader.source, file_name, sections_display, option_name, value_type
                )
            )
            return

        items = value['items']
        if not isinstance(items, dict):
            loader.errors.append(
                '{}, {}, {}{}: Attribute `items` for `type` {} must be a mapping object'.format(
                    loader.source, file_name, sections_display, option_name, value_type
                )
            )
            return

        value_validator(items, loader, file_name, sections_display, option_name, depth=depth + 1)
    elif value_type == 'object':
        if 'example' not in value:
            if not depth:
                value['example'] = {}
        elif not isinstance(value['example'], dict):
            loader.errors.append(
                '{}, {}, {}{}: Attribute `example` for `type` {} must be a mapping object'.format(
                    loader.source, file_name, sections_display, option_name, value_type
                )
            )

        required = value.get('required')
        if 'required' in value:
            if not isinstance(required, list):
                loader.errors.append(
                    '{}, {}, {}{}: Attribute `required` for `type` {} must be an array'.format(
                        loader.source, file_name, sections_display, option_name, value_type
                    )
                )
                required = None
            elif not required:
                loader.errors.append(
                    '{}, {}, {}{}: Remove attribute `required` for `type` {} if no properties are required'.format(
                        loader.source, file_name, sections_display, option_name, value_type
                    )
                )
            elif len(required) - len(set(required)):
                loader.errors.append(
                    '{}, {}, {}{}: All entries in attribute `required` for `type` {} must be unique'.format(
                        loader.source, file_name, sections_display, option_name, value_type
                    )
                )

        properties = value.setdefault('properties', [])
        if not isinstance(properties, list):
            loader.errors.append(
                '{}, {}, {}{}: Attribute `properties` for `type` {} must be an array'.format(
                    loader.source, file_name, sections_display, option_name, value_type
                )
            )
            return

        new_depth = depth + 1
        property_names = []
        for prop in properties:
            if not isinstance(prop, dict):
                loader.errors.append(
                    '{}, {}, {}{}: Every entry in `properties` for `type` {} must be a mapping object'.format(
                        loader.source, file_name, sections_display, option_name, value_type
                    )
                )

            if 'name' not in prop:
                loader.errors.append(
                    '{}, {}, {}{}: Every entry in `properties` for `type` {} must contain a `name` attribute'.format(
                        loader.source, file_name, sections_display, option_name, value_type
                    )
                )
                continue

            name = prop['name']
            if not isinstance(name, str):
                loader.errors.append(
                    '{}, {}, {}{}: Attribute `name` for `type` {} must be a string'.format(
                        loader.source, file_name, sections_display, option_name, value_type
                    )
                )
                continue

            property_names.append(name)

            value_validator(prop, loader, file_name, sections_display, option_name, depth=new_depth)

        if len(property_names) - len(set(property_names)):
            loader.errors.append(
                '{}, {}, {}{}: All entries in attribute `properties` for `type` {} must have unique names'.format(
                    loader.source, file_name, sections_display, option_name, value_type
                )
            )

        if required and set(required).difference(property_names):
            loader.errors.append(
                '{}, {}, {}{}: All entries in attribute `required` for `type` '
                '{} must be defined in the`properties` attribute'.format(
                    loader.source, file_name, sections_display, option_name, value_type
                )
            )
    else:
        loader.errors.append(
            '{}, {}, {}{}: Unknown type `{}`'.format(
                loader.source, file_name, sections_display, option_name, value_type
            )
        )
