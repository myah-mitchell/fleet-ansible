"""Fill in values in a fleet-stacks komodo.env file, and quote it for TOML."""

import re

from ansible.errors import AnsibleFilterError


def komodo_env(text, values, optional=None):
    """Return text with each `KEY:` line in values set to its value.

    komodo.env lines read `KEY: value`, and a key the stack does not use has no
    line at all. Keys in `values` must have a line, so a misspelt override
    stops the run instead of being dropped. Keys in `optional` are set where
    the file has them and skipped where it does not, which suits the values
    every stack is offered, such as SERVER_NAME or TRAEFIK_AUTH_CHAIN.
    Comments, blank lines and [[...]] references pass through unchanged for
    Komodo to resolve.
    """
    optional = optional or {}
    wanted = dict(optional)
    wanted.update(values or {})
    seen = set()
    out = []
    for line in text.splitlines():
        match = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s*:', line)
        if match and match.group(1) in wanted:
            key = match.group(1)
            seen.add(key)
            out.append('%s: %s' % (key, wanted[key]))
        else:
            out.append(line)
    missing = sorted(set(values or {}) - seen)
    if missing:
        raise AnsibleFilterError(
            'komodo.env has no line for %s' % ', '.join(missing))
    return '\n'.join(out) + '\n'


def _toml_basic(text):
    out = []
    for ch in text:
        if ch == '"':
            out.append('\\"')
        elif ch == '\\':
            out.append('\\\\')
        elif ch == '\n':
            out.append('\\n')
        elif ch == '\t':
            out.append('\\t')
        elif ord(ch) < 0x20 or ord(ch) == 0x7f:
            out.append('\\u%04x' % ord(ch))
        else:
            out.append(ch)
    return '"' + ''.join(out) + '"'


def toml_string(value):
    """Return value as a TOML string.

    Text over several lines, such as a Stack's Environment, becomes a
    multi-line literal string, which keeps it readable in a diff and needs no
    escaping. Anything a literal string cannot hold, and every single line,
    becomes an ordinary quoted string.
    """
    text = str(value)
    literal_ok = (
        '\n' in text
        and "'''" not in text
        and not re.search(r'[\x00-\x08\x0b-\x1f\x7f]', text))
    if literal_ok:
        # TOML drops the newline straight after the opening quotes.
        return "'''\n" + text + "'''"
    return _toml_basic(text)


class FilterModule(object):
    def filters(self):
        return {'komodo_env': komodo_env, 'toml_string': toml_string}
