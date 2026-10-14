# `particle_classifier_rules.py`

Groups and rules for the simple Particle Classifier dialog.

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

---

## Constants

| Name | Value |
|------|-------|
| `_MASS_RE` | `re.compile('^(\\d+)')` |
| `_SIMPLE_TOKEN_RE` | `re.compile('\\s*(?:(\\d+[A-Za-z]{1,2})\|([A-Za-z]+)\|([+\\-…` |
| `_KEYWORDS` | `{'or', 'and', 'not', 'oneof'}` |

## Classes

### `_SimpleParser`

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, text, labels)` |  |
| `_peek` | `(self)` |  |
| `_take` | `(self)` |  |
| `_is` | `(self, kind, value=None)` |  |
| `_expect` | `(self, kind, value, what)` |  |
| `parse` | `(self)` |  |
| `_or` | `(self)` |  |
| `_starts_term` | `(self)` |  |
| `_and` | `(self)` |  |
| `_term` | `(self)` |  |
| `_atom` | `(self)` |  |
| `_resolve` | `(self, element, where)` |  |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `isotope_sort_key` | `(label)` | Sort key that puts isotope labels in mass order, then by name. |
| `new_rule` | `()` | An empty rule. |
| `new_group` | `(name, color=None)` | A new group with one empty rule. |
| `recipe_to_expression` | `(must, must_not, any_of=(), one_of=())` | Build an expression from the rows of a rule. |
| `expression_to_recipe` | `(text)` | Split an expression into the rows of a rule. |
| `rule_expression` | `(rule)` | The expression text a rule saves as. |
| `group_signature` | `(group)` | What makes two groups the same, for deciding whether samples share groups. |
| `_rule_from_definition` | `(d)` |  |
| `groups_from_definitions` | `(definitions, groups, sample_names)` | Turn node definitions into per-sample groups. |
| `definitions_from_groups` | `(groups_by_sample, sample_names, previous_definitions=None, previous_g` | Build node definitions and the group colour registry from groups. |
| `sample_summary` | `(particles, definitions, overlap_mode)` | Particle counts per group for one sample, and how many matched nothing. |
| `rule_notes` | `(rule, labels=None)` | Problems and notes about one rule, for showing under the editor. |
| `remove_isotopes` | `(rule, isotopes)` | Take isotopes out of a rule (used for isotopes a sample did not measure). |
| `has_unresolved_issues` | `(definitions, labels_by_sample)` | Whether any definition has a syntax error, a contradiction, or an |
| `confound_pair_key` | `(d_a, d_b)` | Order-independent identity of an overlapping pair of definitions. |
| `confound_key_from_record` | `(rec)` | The :func:`confound_pair_key` of a saved dismissal record. |
| `confound_record` | `(key)` | A saved dismissal record for a :func:`confound_pair_key`. |
| `overlapping_pairs` | `(definitions, connected_samples, dismissed_keys)` | Pairs of definitions on the same sample that can match the same particle. |
| `_simple_tokens` | `(text)` |  |
| `_canonical` | `(ast)` |  |
| `parse_simple` | `(text, labels=None)` | Read the simple text syntax and return the classic expression. |
| `_simple` | `(ast, nested=False)` |  |
| `to_simple` | `(text)` | Show a classic expression in the simple text syntax. |
| `combinations` | `(particles)` | Every isotope combination found in a sample, most common first. |
| `combination_groups` | `(isotopes, definitions, overlap_mode)` | The groups a particle with exactly these isotopes falls in. |
