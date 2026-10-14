# -*- coding: utf-8 -*-
"""Groups and rules for the simple Particle Classifier dialog.

A *group* is what the simple dialog shows in its Groups list: a name, a
colour, and one or more alternative *rules*. A particle belongs to the group
when it matches any of its rules. Each rule becomes one node definition, so
a group with two rules is exactly the classic "group that pools several
definitions". Groups convert to and from the node's definition dicts (see
:class:`tools.particle_classifier_node.ParticleClassifierNode`), so the
node, the relabelling pass and saved projects are unchanged.

Shapes::

    group = {'name': str, 'color': str | None, 'rules': [rule, ...]}
    rule = {
        'must': [isotope, ...],
        'any': [isotope, ...],
        'one': [isotope, ...],
        'must_not': [isotope, ...],
        'exact': bool,
        'text': str,
        'text_mode': bool,
        'orig': tuple | None,
    }

``any`` holds the "at least one of" isotopes and ``one`` the "exactly one
of" isotopes. A ``text_mode`` rule carries a free expression in ``text``
(several or-groups, nested brackets, a NOT around more than one isotope:
logic the rows cannot show). ``orig`` remembers the loaded
``(must, any, one, must_not, text)`` so an unchanged rule saves back its
exact original expression text.

Pure Python, no Qt widgets.
"""

from __future__ import annotations

import copy as _copy
import re

from tools.particle_classifier_expr import (
    parse, ExpressionSyntaxError, Isotope, And, Or, Xor, Not,
    referenced_isotopes, classify_formula, find_confound,
)
from tools.particle_classifier_node import new_definition_id
from tools.particle_classifier_relabel import (
    classify_particle, _parse_definitions,
)

_MASS_RE = re.compile(r'^(\d+)')


def isotope_sort_key(label):
    """Sort key that puts isotope labels in mass order, then by name.

    Args:
        label (str): An isotope label such as ``'107Ag'``.

    Returns:
        tuple: ``(mass, label)``; labels without a leading mass sort last.
    """
    m = _MASS_RE.match(label or '')
    return (int(m.group(1)) if m else 10 ** 6, label or '')


def new_rule():
    """An empty rule."""
    return {'must': [], 'any': [], 'one': [], 'must_not': [], 'exact': False,
            'text': '', 'text_mode': False, 'orig': None}


def new_group(name, color=None):
    """A new group with one empty rule.

    Args:
        name (str): Group name.
        color (str | None): Group colour.

    Returns:
        dict: The group.
    """
    return {'name': name, 'color': color, 'rules': [new_rule()]}


def recipe_to_expression(must, must_not, any_of=(), one_of=()):
    """Build an expression from the rows of a rule.

    Args:
        must (list): Isotopes the particle must contain.
        must_not (list): Isotopes the particle must not contain.
        any_of (list): Isotopes of which the particle must contain at least one.
        one_of (list): Isotopes of which the particle must contain exactly one.

    Returns:
        str: e.g. ``'48Ti+[60Ni, 52Cr]+{107Ag; 63Cu}+!(55Mn)'``; empty when
            all lists are empty.
    """
    parts = list(must)
    if any_of:
        parts.append('[' + ', '.join(any_of) + ']')
    if one_of:
        parts.append('{' + '; '.join(one_of) + '}')
    parts += [f"!({iso})" for iso in must_not]
    return '+'.join(parts)


def expression_to_recipe(text):
    """Split an expression into the rows of a rule.

    Args:
        text (str): Expression text.

    Returns:
        tuple | None: ``(must, any_of, one_of, must_not)``, or None when the
            expression is invalid or uses logic the rows cannot show (more
            than one any-of or one-of group, nested groups, a NOT around more
            than one isotope).
    """
    if not (text or '').strip():
        return [], [], [], []
    try:
        ast = parse(text)
    except ExpressionSyntaxError:
        return None
    terms = ast.terms if isinstance(ast, And) else [ast]
    must, any_of, one_of, must_not = [], [], [], []
    seen_any = seen_one = False
    for term in terms:
        if isinstance(term, Isotope):
            if term.label not in must:
                must.append(term.label)
        elif isinstance(term, Not) and isinstance(term.inner, Isotope):
            if term.inner.label not in must_not:
                must_not.append(term.inner.label)
        elif (isinstance(term, Or) and not seen_any
              and all(isinstance(b, Isotope) for b in term.branches)):
            seen_any = True
            for b in term.branches:
                if b.label not in any_of:
                    any_of.append(b.label)
        elif (isinstance(term, Xor) and not seen_one
              and all(isinstance(b, Isotope) for b in term.branches)):
            seen_one = True
            for b in term.branches:
                if b.label not in one_of:
                    one_of.append(b.label)
        else:
            return None
    rows = [set(must), set(any_of), set(one_of), set(must_not)]
    if sum(len(r) for r in rows) != len(set().union(*rows)):
        return None
    return must, any_of, one_of, must_not


def rule_expression(rule):
    """The expression text a rule saves as.

    An unchanged loaded rule returns its original text, so reopening and
    pressing OK never rewrites a user's expression.

    Args:
        rule (dict): A rule.

    Returns:
        str: Expression text.
    """
    if rule.get('text_mode'):
        return rule.get('text') or ''
    orig = rule.get('orig')
    rows = (list(rule['must']), list(rule.get('any') or []),
            list(rule.get('one') or []), list(rule['must_not']))
    if orig and tuple(list(x) for x in orig[:4]) == rows:
        return orig[4]
    return recipe_to_expression(rule['must'], rule['must_not'],
                                rule.get('any') or [], rule.get('one') or [])


def group_signature(group):
    """What makes two groups the same, for deciding whether samples share groups.

    Args:
        group (dict): A group.

    Returns:
        tuple: Comparable identity of the group (colour excluded, colours
            are shared across samples anyway).
    """
    return (group['name'], tuple(
        (rule_expression(r).replace(' ', ''), bool(r.get('exact')))
        for r in group['rules']))


def _rule_from_definition(d):
    rule = new_rule()
    text = d.get('expression_text') or ''
    rule['exact'] = d.get('match_mode') == 'exact'
    recipe = expression_to_recipe(text)
    if recipe is None:
        rule['text_mode'] = True
        rule['text'] = text
    else:
        rule['must'], rule['any'], rule['one'], rule['must_not'] = recipe
        rule['text'] = text
        rule['orig'] = tuple(list(x) for x in recipe) + (text,)
    return rule


def groups_from_definitions(definitions, groups, sample_names):
    """Turn node definitions into per-sample groups.

    Definitions sharing a group name on one sample become one group with
    several rules; an ungrouped definition becomes a group named after its
    expression.

    Args:
        definitions (list): Node definition dicts.
        groups (dict): ``{group_name: color}``.
        sample_names (list): Connected sample names, in display order.

    Returns:
        tuple: ``(groups_by_sample, shared)``. ``groups_by_sample`` maps
            every name in ``sample_names`` to its ordered group list;
            ``shared`` is True when every sample has the same groups (or
            none exist).
    """
    groups = groups or {}
    groups_by_sample = {}
    for sample in sample_names:
        order, by_key = [], {}
        for d in definitions or []:
            if d.get('target_sample') != sample:
                continue
            key = ('group', d['group_name']) if d.get('group_name') else ('def', d.get('id'))
            if key not in by_key:
                by_key[key] = []
                order.append(key)
            by_key[key].append(d)
        out = []
        for key in order:
            defs = by_key[key]
            first = defs[0]
            if key[0] == 'group':
                name, color = first['group_name'], groups.get(first['group_name'])
            else:
                name, color = (first.get('expression_text') or '').strip(), first.get('color')
            out.append({'name': name, 'color': color,
                        'rules': [_rule_from_definition(d) for d in defs]})
        groups_by_sample[sample] = out

    if not sample_names:
        return groups_by_sample, True
    signatures = [[group_signature(g) for g in groups_by_sample[s]] for s in sample_names]
    return groups_by_sample, all(sig == signatures[0] for sig in signatures)


def definitions_from_groups(groups_by_sample, sample_names, previous_definitions=None,
                            previous_groups=None):
    """Build node definitions and the group colour registry from groups.

    Definitions for samples that are not connected right now are kept as
    they were, so reconnecting a sample later restores its setup. Existing
    definition ids are reused, in order, when the same group returns on the
    same sample, so dismissed overlap warnings stay attached. Empty rules
    and unnamed groups are skipped.

    Args:
        groups_by_sample (dict): ``{sample_name: [group, ...]}``.
        sample_names (list): Connected sample names.
        previous_definitions (list | None): The node's definitions before
            this edit.
        previous_groups (dict | None): The node's group colours before this
            edit.

    Returns:
        tuple: ``(definitions, groups)`` in the node's format.
    """
    previous_definitions = previous_definitions or []
    previous_groups = previous_groups or {}
    connected = set(sample_names)
    old_ids = {}
    for d in previous_definitions:
        name = d.get('group_name') or (d.get('expression_text') or '').strip()
        old_ids.setdefault((d.get('target_sample'), name), []).append(d['id'])

    out = [_copy.deepcopy(d) for d in previous_definitions
           if d.get('target_sample') not in connected]
    color_registry = {}
    for d in out:
        name = d.get('group_name')
        if name and name in previous_groups:
            color_registry[name] = previous_groups[name]

    for sample in sample_names:
        for group in groups_by_sample.get(sample) or []:
            name = (group.get('name') or '').strip()
            if not name:
                continue
            reuse = old_ids.get((sample, name), [])
            wrote = False
            for rule in group.get('rules') or []:
                expr = rule_expression(rule)
                if not expr.strip():
                    continue
                out.append({
                    'id': reuse.pop(0) if reuse else new_definition_id(),
                    'target_sample': sample,
                    'expression_text': expr,
                    'match_mode': 'exact' if rule.get('exact') else 'partial',
                    'group_name': name,
                    'color': None,
                })
                wrote = True
            if wrote:
                color_registry[name] = group.get('color')
    return out, color_registry


def sample_summary(particles, definitions, overlap_mode):
    """Particle counts per group for one sample, and how many matched nothing.

    A particle counts once per group even when several rules of that group
    match it.

    Args:
        particles (list): One sample's particle dicts.
        definitions (list): That sample's definitions, in priority order.
        overlap_mode (str): ``'double_count'`` or ``'priority'``.

    Returns:
        tuple: ``({group_name: count}, n_unmatched, n_total)``.
    """
    parsed = _parse_definitions(definitions)
    per_group = {}
    unmatched = 0
    for p in particles or []:
        matched = classify_particle(p, definitions, overlap_mode, parsed=parsed)
        if not matched:
            unmatched += 1
            continue
        seen = set()
        for d in matched:
            name = d.get('group_name') or (d.get('expression_text') or '').strip()
            if name in seen:
                continue
            seen.add(name)
            per_group[name] = per_group.get(name, 0) + 1
    return per_group, unmatched, len(particles or [])


def rule_notes(rule, labels=None):
    """Problems and notes about one rule, for showing under the editor.

    Args:
        rule (dict): A rule.
        labels (set | None): Isotopes measured in the sample being viewed.

    Returns:
        dict: ``{'error': str | None, 'contradiction': bool,
            'tautology': bool, 'missing': [isotope, ...]}``.
    """
    notes = {'error': None, 'contradiction': False, 'tautology': False, 'missing': []}
    text = rule_expression(rule)
    if not text.strip():
        return notes
    try:
        ast = parse(text)
    except ExpressionSyntaxError as exc:
        notes['error'] = str(exc)
        return notes
    verdict = classify_formula(ast)
    notes['contradiction'] = verdict == 'contradiction'
    notes['tautology'] = verdict == 'tautology'
    if labels is not None:
        notes['missing'] = sorted(referenced_isotopes(ast) - set(labels), key=isotope_sort_key)
    return notes


def remove_isotopes(rule, isotopes):
    """Take isotopes out of a rule (used for isotopes a sample did not measure).

    In text mode each isotope token is removed from the text, as the
    classic editor does; a dangling operator left behind shows up as a
    normal syntax error to fix.

    Args:
        rule (dict): A rule, changed in place.
        isotopes (iterable): Isotope labels to remove.
    """
    isotopes = set(isotopes)
    if rule.get('text_mode'):
        text = rule.get('text') or ''
        for iso in isotopes:
            text = text.replace(iso, '')
        rule['text'] = text
        return
    rule['must'] = [i for i in rule['must'] if i not in isotopes]
    rule['any'] = [i for i in rule.get('any') or [] if i not in isotopes]
    rule['one'] = [i for i in rule.get('one') or [] if i not in isotopes]
    rule['must_not'] = [i for i in rule['must_not'] if i not in isotopes]


def has_unresolved_issues(definitions, labels_by_sample):
    """Whether any definition has a syntax error, a contradiction, or an
    isotope its connected sample did not measure.

    Args:
        definitions (list): Node definition dicts.
        labels_by_sample (dict): ``{sample_name: set_of_isotope_labels}``
            for connected samples.

    Returns:
        bool: True when the node should show its warning badge.
    """
    for d in definitions or []:
        text = d.get('expression_text') or ''
        if not text.strip():
            continue
        try:
            ast = parse(text)
        except ExpressionSyntaxError:
            return True
        if classify_formula(ast) == 'contradiction':
            return True
        labels = labels_by_sample.get(d.get('target_sample'))
        if labels is not None and referenced_isotopes(ast) - labels:
            return True
    return False


def confound_pair_key(d_a, d_b):
    """Order-independent identity of an overlapping pair of definitions.

    Same key as the classic editor's, so a pair dismissed in either editor
    stays dismissed in the other. Editing either expression or match mode
    makes it a new pair.

    Returns:
        tuple: ``(id_a, id_b, expr_a, expr_b, mode_a, mode_b)``.
    """
    a, b = sorted((d_a, d_b), key=lambda d: d['id'])
    return (a['id'], b['id'], a.get('expression_text', ''),
            b.get('expression_text', ''), a.get('match_mode', 'partial'),
            b.get('match_mode', 'partial'))


def confound_key_from_record(rec):
    """The :func:`confound_pair_key` of a saved dismissal record."""
    return (rec.get('id_a'), rec.get('id_b'),
            rec.get('expr_a', ''), rec.get('expr_b', ''),
            rec.get('mode_a', 'partial'), rec.get('mode_b', 'partial'))


def confound_record(key):
    """A saved dismissal record for a :func:`confound_pair_key`."""
    return {'id_a': key[0], 'id_b': key[1], 'expr_a': key[2], 'expr_b': key[3],
            'mode_a': key[4], 'mode_b': key[5]}


def overlapping_pairs(definitions, connected_samples, dismissed_keys):
    """Pairs of definitions on the same sample that can match the same particle.

    Same check as the classic editor's overlap warning.

    Args:
        definitions (list): Node definition dicts.
        connected_samples (set): Names of samples connected right now.
        dismissed_keys (set): Keys the user chose never to be warned about.

    Returns:
        list: ``(def_a, def_b, witness_isotopes, key)`` tuples.
    """
    by_sample = {}
    for d in definitions or []:
        if d.get('target_sample') in connected_samples:
            by_sample.setdefault(d['target_sample'], []).append(d)
    pairs, seen = [], set()
    for defs in by_sample.values():
        parsed = []
        for d in defs:
            text = d.get('expression_text') or ''
            if not text.strip():
                continue
            try:
                parsed.append((d, parse(text)))
            except ExpressionSyntaxError:
                continue
        for i, (d_a, ast_a) in enumerate(parsed):
            for d_b, ast_b in parsed[i + 1:]:
                witness = find_confound(ast_a, ast_b, d_a.get('match_mode', 'partial'),
                                        d_b.get('match_mode', 'partial'))
                if witness is None:
                    continue
                key = confound_pair_key(d_a, d_b)
                if key in dismissed_keys or key in seen:
                    continue
                seen.add(key)
                pairs.append((d_a, d_b, witness, key))
    return pairs


_SIMPLE_TOKEN_RE = re.compile(r'\s*(?:(\d+[A-Za-z]{1,2})|([A-Za-z]+)|([+\-\u2212(),]))')
_KEYWORDS = {'or', 'and', 'not', 'oneof'}


def _simple_tokens(text):
    tokens = []
    pos = 0
    text = text or ''
    while pos < len(text):
        if text[pos:].strip() == '':
            break
        m = _SIMPLE_TOKEN_RE.match(text, pos)
        if not m or m.end() == pos:
            bad = text[pos:].lstrip()[:1]
            raise ExpressionSyntaxError(f"Unexpected character {bad!r}", pos)
        iso, word, sym = m.groups()
        start = m.start(1) if iso else m.start(2) if word else m.start(3)
        if iso:
            num = re.match(r'\d+', iso).group(0)
            sym_part = iso[len(num):]
            tokens.append(('ISO', num + sym_part[0].upper() + sym_part[1:].lower(), start))
        elif word:
            low = word.lower()
            if low in _KEYWORDS:
                tokens.append(('KW', low, start))
            else:
                tokens.append(('ELEM', word[0].upper() + word[1:].lower(), start))
        else:
            tokens.append(('SYM', '-' if sym == '\u2212' else sym, start))
        pos = m.end()
    return tokens


class _SimpleParser:
    def __init__(self, text, labels):
        self.tokens = _simple_tokens(text)
        self.i = 0
        self.labels = set(labels or ())

    def _peek(self):
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def _take(self):
        tok = self._peek()
        self.i += 1
        return tok

    def _is(self, kind, value=None):
        tok = self._peek()
        return tok is not None and tok[0] == kind and (value is None or tok[1] == value)

    def _expect(self, kind, value, what):
        if not self._is(kind, value):
            tok = self._peek()
            where = tok[2] if tok else None
            found = repr(tok[1]) if tok else "the end"
            raise ExpressionSyntaxError(f"Expected {what}, found {found}", where)
        return self._take()

    def parse(self):
        if not self.tokens:
            raise ExpressionSyntaxError("Empty expression")
        node = self._or()
        if self._peek() is not None:
            tok = self._peek()
            raise ExpressionSyntaxError(f"Unexpected {tok[1]!r}", tok[2])
        return node

    def _or(self):
        branches = [self._and()]
        while self._is('KW', 'or'):
            self._take()
            branches.append(self._and())
        return branches[0] if len(branches) == 1 else Or(branches)

    def _starts_term(self):
        tok = self._peek()
        if tok is None:
            return False
        kind, value = tok[0], tok[1]
        return (kind in ('ISO', 'ELEM')
                or (kind == 'SYM' and value in '+-(')
                or (kind == 'KW' and value in ('not', 'oneof')))

    def _and(self):
        terms = []
        while True:
            if self._is('KW', 'and') and terms:
                self._take()
            if not self._starts_term():
                break
            terms.append(self._term())
        if not terms:
            tok = self._peek()
            found = repr(tok[1]) if tok else "the end"
            raise ExpressionSyntaxError(f"Expected an isotope, found {found}",
                                        tok[2] if tok else None)
        return terms[0] if len(terms) == 1 else And(terms)

    def _term(self):
        if self._is('SYM', '+'):
            self._take()
            return self._atom()
        if self._is('SYM', '-') or self._is('KW', 'not'):
            self._take()
            return Not(self._atom())
        return self._atom()

    def _atom(self):
        tok = self._peek()
        if tok is None:
            raise ExpressionSyntaxError("Expected an isotope, found the end")
        kind, value, where = tok
        if kind == 'ISO':
            self._take()
            return Isotope(value)
        if kind == 'ELEM':
            self._take()
            return Isotope(self._resolve(value, where))
        if kind == 'SYM' and value == '(':
            self._take()
            node = self._or()
            self._expect('SYM', ')', "')'")
            return node
        if kind == 'KW' and value == 'oneof':
            self._take()
            self._expect('SYM', '(', "'(' after oneof")
            branches = [self._or()]
            while self._is('SYM', ','):
                self._take()
                branches.append(self._or())
            self._expect('SYM', ')', "')'")
            if len(branches) < 2:
                raise ExpressionSyntaxError("oneof needs at least two choices", where)
            return Xor(branches)
        raise ExpressionSyntaxError(f"Expected an isotope, found {value!r}", where)

    def _resolve(self, element, where):
        matches = sorted((lbl for lbl in self.labels
                          if re.fullmatch(r'\d+' + re.escape(element), lbl)),
                         key=isotope_sort_key)
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise ExpressionSyntaxError(f"No {element} isotope was measured in this data", where)
        raise ExpressionSyntaxError(
            f"{element} is measured as {', '.join(matches)}: write the one you mean", where)


def _canonical(ast):
    if isinstance(ast, Isotope):
        return ast.label
    if isinstance(ast, Not):
        return f"!({_canonical(ast.inner)})"
    if isinstance(ast, And):
        parts = []
        for term in ast.terms:
            if isinstance(term, And):
                parts.extend(_canonical(t) for t in term.terms)
            else:
                parts.append(_canonical(term))
        return '+'.join(parts)
    if isinstance(ast, Or):
        return '[' + ', '.join(_canonical(b) for b in ast.branches) + ']'
    if isinstance(ast, Xor):
        return '{' + '; '.join(_canonical(b) for b in ast.branches) + '}'
    raise TypeError(f"Unknown AST node type: {type(ast)!r}")


def parse_simple(text, labels=None):
    """Read the simple text syntax and return the classic expression.

    Simple syntax: ``+60Ni`` has, ``-56Fe`` has not, terms side by side
    mean "and", ``or`` between alternatives, ``oneof(+a, +b)`` exactly one,
    parentheses group. An element name such as ``Fe`` stands for the one
    isotope of it in ``labels``. The classic syntax is accepted as well.

    Args:
        text (str): What the user typed.
        labels (iterable | None): Isotopes measured in the data, used to
            turn element names into isotopes.

    Returns:
        str: The expression in the classic syntax, e.g.
            ``'48Ti+[56Fe, 27Al]'``.

    Raises:
        ExpressionSyntaxError: When the text is neither valid simple nor
            valid classic syntax.
    """
    try:
        return _canonical(_SimpleParser(text, labels).parse())
    except ExpressionSyntaxError as simple_error:
        try:
            parse(text)
        except ExpressionSyntaxError:
            raise simple_error
        return text


def _simple(ast, nested=False):
    if isinstance(ast, Isotope):
        return '+' + ast.label
    if isinstance(ast, Not):
        inner = ast.inner
        if isinstance(inner, Isotope):
            return '-' + inner.label
        return '-(' + _simple(inner) + ')'
    if isinstance(ast, And):
        return ' '.join(_simple(t, nested=True) for t in ast.terms)
    if isinstance(ast, Or):
        body = ' or '.join(_simple(b) for b in ast.branches)
        return f"({body})" if nested else body
    if isinstance(ast, Xor):
        return 'oneof(' + ', '.join(_simple(b) for b in ast.branches) + ')'
    raise TypeError(f"Unknown AST node type: {type(ast)!r}")


def to_simple(text):
    """Show a classic expression in the simple text syntax.

    Args:
        text (str): Classic expression, e.g. ``'48Ti+[56Fe, 27Al]'``.

    Returns:
        str: e.g. ``'+48Ti (+56Fe or +27Al)'``; the text unchanged when it
            does not parse.
    """
    if not (text or '').strip():
        return ''
    try:
        return _simple(parse(text))
    except ExpressionSyntaxError:
        return text


def combinations(particles):
    """Every isotope combination found in a sample, most common first.

    Args:
        particles (list): One sample's particle dicts.

    Returns:
        list: ``[(isotopes_tuple, count), ...]``; isotopes in mass order.
    """
    counts = {}
    for p in particles or []:
        key = tuple(sorted((p.get('elements') or {}).keys(), key=isotope_sort_key))
        if key:
            counts[key] = counts.get(key, 0) + 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], len(kv[0]), kv[0]))


def combination_groups(isotopes, definitions, overlap_mode):
    """The groups a particle with exactly these isotopes falls in.

    Args:
        isotopes (iterable): The particle's isotopes.
        definitions (list): One sample's definitions, in priority order.
        overlap_mode (str): ``'double_count'`` or ``'priority'``.

    Returns:
        list: Group names, in priority order, without repeats.
    """
    particle = {'elements': {iso: 1.0 for iso in isotopes}}
    names = []
    for d in classify_particle(particle, definitions, overlap_mode):
        name = d.get('group_name') or (d.get('expression_text') or '').strip()
        if name not in names:
            names.append(name)
    return names
