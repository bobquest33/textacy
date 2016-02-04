"""
Set of small utility functions that take Spacy objects as input.
"""
from __future__ import absolute_import, division, print_function, unicode_literals

from itertools import takewhile
from spacy.parts_of_speech import NOUN, VERB
from spacy.tokens.token import Token as spacy_token
from spacy.tokens.span import Span as spacy_span

from ds_tools.nlp.text_utils import is_acronym
from ds_tools.nlp.regexes_etc import AUX_DEPS, SUBJ_DEPS, OBJ_DEPS


def is_plural_noun(token):
    """
    Returns True if token is a plural noun, False otherwise.

    Args:
        token (:class:`spacy.Token()`): parent document must have POS information

    Returns:
        bool
    """
    if token.doc.is_tagged is False:
        raise ValueError('token is not POS-tagged')
    return True if token.pos == NOUN and token.lemma != token.lower else False


def is_negated_verb(token):
    """
    Returns True if verb is negated by one of its (dependency parse) children,
    False otherwise.

    Args:
        token (:class:`spacy.Token()`): parent document must have parse information

    Returns:
        bool

    TODO: generalize to other parts of speech; rule-based is pretty lacking,
    so will probably require training a model; this is an unsolved research problem
    """
    if token.doc.is_parsed is False:
        raise ValueError('token is not parsed')
    if token.pos == VERB and any(c.dep_ == 'neg' for c in token.children):
        return True
    # if (token.pos == NOUN
    #         and any(c.dep_ == 'det' and c.lower_ == 'no' for c in token.children)):
    #     return True
    return False


def preserve_case(token):
    """
    Returns True if `token` is a proper noun or acronym, False otherwise.

    Args:
        token (:class:`spacy.Token()`): parent document must have POS information

    Returns:
        bool

    TODO: use universal pos PROPN instead of english-specific tags as soon as
    Honnibal decides to include them in his model...
    """
    if token.doc.is_tagged is False:
        raise ValueError('token is not POS-tagged')
    return token.tag_ in {'NNP', 'NNPS'} or is_acronym(token.text)


def normalized_str(token):
    """
    Return as-is text for tokens that are proper nouns or acronyms, lemmatized
    text for everything else.

    Args:
        token (:class:`spacy.Token()` or :class:`spacy.Span()`)

    Returns:
        str
    """
    if isinstance(token, spacy_token):
        return token.text if preserve_case(token) else token.lemma_
    elif isinstance(token, spacy_span):
        return ' '.join(subtok.text if preserve_case(subtok) else subtok.lemma_
                        for subtok in token)
    else:
        msg = 'Input must be a spacy Token or Span, not {}.'.format(type(token))
        raise TypeError(msg)


def merge_spans(spans, doc):
    """
    Merge spans so that each only takes up a single token. Since each Span is
    a view into the doc, merging one invalidates the others. (This will get fixed!)
    The temporary solution is to gather the information first, before merging.
    NB: This modifies `doc` in-place!

    Args:
        spans (iterable[:class:`spacy.Span()`])
        doc (:class:`spacy.Doc()`)
    """
    for span_tuple in (_span_to_tuple(span) for span in spans):
        doc.merge(*span_tuple)


def _span_to_tuple(span):
    start = span[0].idx
    end = span[-1].idx + len(span[-1])
    tag = span.root.tag_
    text = span.text
    label = span.label_
    return (start, end, tag, text, label)


def get_main_verbs_of_sent(sent):
    """Return the main (non-auxiliary) verbs in a sentence."""
    return [tok for tok in sent
            if tok.pos == VERB and tok.dep_ not in {'aux', 'auxpass'}]


def get_subjects_of_verb(verb):
    """Return all subjects of a verb according to the dependency parse."""
    subjs = [tok for tok in verb.lefts
             if tok.dep_ in SUBJ_DEPS]
    # get additional conjunct subjects
    subjs.extend(tok for subj in subjs for tok in _get_conjuncts(subj))
    return subjs


def get_objects_of_verb(verb):
    """
    Return all objects of a verb according to the dependency parse,
    including open clausal complements.
    """
    objs = [tok for tok in verb.rights
            if tok.dep_ in OBJ_DEPS]
    # get open clausal complements (xcomp)
    objs.extend(tok for tok in verb.rights
                if tok.dep_ == 'xcomp')
    # get additional conjunct objects
    objs.extend(tok for obj in objs for tok in _get_conjuncts(obj))
    return objs


def _get_conjuncts(tok):
    """
    Return conjunct dependents of the leftmost conjunct in a coordinated phrase,
    e.g. "Burton, [Dan], and [Josh] ...".
    """
    return [right for right in tok.rights
            if right.dep_ == 'conj']


def get_span_for_compound_noun(noun):
    """
    Return document indexes spanning all (adjacent) tokens
    in a compound noun.
    """
    min_i = noun.i - sum(1 for _ in takewhile(lambda x: x.dep_ == 'compound',
                                              reversed(list(noun.lefts))))
    return (min_i, noun.i)


def get_span_for_verb_auxiliaries(verb):
    """
    Return document indexes spanning all (adjacent) tokens
    around a verb that are auxiliary verbs or negations.
    """
    min_i = verb.i - sum(1 for _ in takewhile(lambda x: x.dep_ in AUX_DEPS,
                                              reversed(list(verb.lefts))))
    max_i = verb.i + sum(1 for _ in takewhile(lambda x: x.dep_ in AUX_DEPS,
                                              verb.rights))
    return (min_i, max_i)
