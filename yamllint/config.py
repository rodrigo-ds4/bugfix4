# Copyright (C) 2016 Adrien Vergé
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import fileinput
import os.path

import pathspec
import yaml

import yamllint.rules


class YamlLintConfigError(Exception):
    pass


class YamlLintConfig:
    def __init__(self, content=None, file=None):
        assert (content is None) ^ (file is None)

        self.ignore = None

        self.yaml_files = pathspec.PathSpec.from_lines(
            'gitwildmatch', ['*.yaml', '*.yml', '.yamllint'])

        self.locale = None

        if file is not None:
            with open(file) as f:
                content = f.read()

        self.parse(content)
        self.validate()

    def is_file_ignored(self, filepath):
        return self.ignore and self.ignore.match_file(filepath)

    def is_yaml_file(self, filepath):
        return self.yaml_files.match_file(os.path.basename(filepath))

    def enabled_rules(self, filepath):
        return [yamllint.rules.get(id) for id, val in self.rules.items()
                if val is not False and (
                    filepath is None or 'ignore' not in val or
                    not val['ignore'].match_file(filepath))]

    def extend(self, base_config):
        assert isinstance(base_config, YamlLintConfig)

        for rule in self.rules:
            if (isinstance(self.rules[rule], dict) and
                    rule in base_config.rules and
                    base_config.rules[rule] is not False):
                base_config.rules[rule].update(self.rules[rule])
            else:
                base_config.rules[rule] = self.rules[rule]

        self.rules = base_config.rules

        if base_config.ignore is not None:
            self.ignore = base_config.ignore

    def parse(self, raw_content):
        """Parse YAML configuration content and set up rules and other options."""
        # Check for empty or whitespace-only configuration
        if not raw_content or not raw_content.strip():
            raise YamlLintConfigError('invalid config: not a dict')
            
        try:
            conf = yaml.safe_load(raw_content) or {}
        except yaml.error.YAMLError as e:
            raise YamlLintConfigError(f'invalid YAML syntax: {e}')

        if not isinstance(conf, dict):
            raise YamlLintConfigError('invalid config: not a dict')

        # Handle extends directive
        if 'extends' in conf:
            base_file = get_extended_config_file(conf['extends'])
            try:
                base_config = YamlLintConfig(file=base_file)
            except IOError as e:
                raise YamlLintConfigError(
                    f'invalid config: extends: "{base_file}": {e}')
            self.rules = base_config.rules
            self.ignore = base_config.ignore
            self.locale = base_config.locale
        else:
            self.rules = {}

        # Handle rules
        if 'rules' in conf:
            if not isinstance(conf['rules'], dict):
                raise YamlLintConfigError('invalid config: rules should be a dict')
            for rule_name, rule_conf in conf['rules'].items():
                if rule_conf is None:
                    continue
                if rule_conf == 'enable':
                    self.rules[rule_name] = {}
                elif rule_conf == 'disable':
                    self.rules[rule_name] = False
                else:
                    self.rules[rule_name] = rule_conf

        # Handle ignore patterns
        if 'ignore' in conf:
            if isinstance(conf['ignore'], str):
                self.ignore = pathspec.PathSpec.from_lines(
                    'gitwildmatch', conf['ignore'].splitlines())
            elif isinstance(conf['ignore'], list):
                self.ignore = pathspec.PathSpec.from_lines(
                    'gitwildmatch', conf['ignore'])
            else:
                raise YamlLintConfigError(
                    'invalid config: ignore should contain file patterns')

        # Handle yaml-files patterns
        if 'yaml-files' in conf:
            if isinstance(conf['yaml-files'], str):
                self.yaml_files = pathspec.PathSpec.from_lines(
                    'gitwildmatch', conf['yaml-files'].splitlines())
            elif isinstance(conf['yaml-files'], list):
                self.yaml_files = pathspec.PathSpec.from_lines(
                    'gitwildmatch', conf['yaml-files'])
            else:
                raise YamlLintConfigError(
                    'invalid config: yaml-files should contain file patterns')

        # Handle locale
        if 'locale' in conf:
            self.locale = conf['locale']
    def validate(self):
        for id in self.rules:
            try:
                rule = yamllint.rules.get(id)
            except Exception as e:
                raise YamlLintConfigError(f'invalid config: {e}') from e

            self.rules[id] = validate_rule_conf(rule, self.rules[id])


def validate_rule_conf(rule, conf):
    if conf is False:  # disable
        return False

    if isinstance(conf, dict):
        if ('ignore-from-file' in conf and not isinstance(
                conf['ignore-from-file'], pathspec.pathspec.PathSpec)):
            if isinstance(conf['ignore-from-file'], str):
                conf['ignore-from-file'] = [conf['ignore-from-file']]
            if not (isinstance(conf['ignore-from-file'], list)
                    and all(isinstance(line, str)
                            for line in conf['ignore-from-file'])):
                raise YamlLintConfigError(
                    'invalid config: ignore-from-file should contain '
                    'valid filename(s), either as a list or string')
            with fileinput.input(conf['ignore-from-file']) as f:
                conf['ignore'] = pathspec.PathSpec.from_lines(
                    'gitwildmatch', f)
        elif ('ignore' in conf and not isinstance(
                conf['ignore'], pathspec.pathspec.PathSpec)):
            if isinstance(conf['ignore'], str):
                conf['ignore'] = pathspec.PathSpec.from_lines(
                    'gitwildmatch', conf['ignore'].splitlines())
            elif (isinstance(conf['ignore'], list) and
                    all(isinstance(line, str) for line in conf['ignore'])):
                conf['ignore'] = pathspec.PathSpec.from_lines(
                    'gitwildmatch', conf['ignore'])
            else:
                raise YamlLintConfigError(
                    'invalid config: ignore should contain file patterns')

        if 'level' not in conf:
            conf['level'] = 'error'
        elif conf['level'] not in ('error', 'warning'):
            raise YamlLintConfigError(
                'invalid config: level should be "error" or "warning"')

        options = getattr(rule, 'CONF', {})
        options_default = getattr(rule, 'DEFAULT', {})
        for optkey in conf:
            if optkey in ('ignore', 'ignore-from-file', 'level'):
                continue
            if optkey not in options:
                raise YamlLintConfigError(
                    f'invalid config: unknown option "{optkey}" for rule '
                    f'"{rule.ID}"')
            # Example: CONF = {option: (bool, 'mixed')}
            #          → {option: true}         → {option: mixed}
            if isinstance(options[optkey], tuple):
                if (conf[optkey] not in options[optkey] and
                        type(conf[optkey]) not in options[optkey]):
                    raise YamlLintConfigError(
                        f'invalid config: option "{optkey}" of "{rule.ID}" '
                        f'should be in {options[optkey]}')
            # Example: CONF = {option: ['flag1', 'flag2', int]}
            #          → {option: [flag1]}      → {option: [42, flag1, flag2]}
            elif isinstance(options[optkey], list):
                if (not isinstance(conf[optkey], list) or
                        any(flag not in options[optkey] and
                            type(flag) not in options[optkey]
                            for flag in conf[optkey])):
                    raise YamlLintConfigError(
                        f'invalid config: option "{optkey}" of "{rule.ID}" '
                        f'should only contain values in {options[optkey]}')
            # Example: CONF = {option: int}
            #          → {option: 42}
            else:
                if not isinstance(conf[optkey], options[optkey]):
                    raise YamlLintConfigError(
                        f'invalid config: option "{optkey}" of "{rule.ID}" '
                        f'should be {options[optkey].__name__}')
        for optkey in options:
            if optkey not in conf:
                conf[optkey] = options_default[optkey]

        if hasattr(rule, 'VALIDATE'):
            res = rule.VALIDATE(conf)
            if res:
                raise YamlLintConfigError(f'invalid config: {rule.ID}: {res}')
    else:
        raise YamlLintConfigError(
            f'invalid config: rule "{rule.ID}": should be either "enable", '
            f'"disable" or a dict')

    return conf


def get_extended_config_file(name):
    # Is it a standard conf shipped with yamllint...
    if '/' not in name:
        std_conf = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                'conf', f'{name}.yaml')

        if os.path.isfile(std_conf):
            return std_conf

    # or a custom conf on filesystem?
    return name
