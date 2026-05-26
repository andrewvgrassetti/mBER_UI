"""
Compatibility patches for NanoBodyBuilder2 (NBB2) / ImmuneBuilder.

Import this module early (before ImmuneBuilder or anarci are used) to apply
HMMER 3.4 / BioPython compatibility patches that prevent TypeErrors during
VHH structure prediction.

Usage in mber-open's nbb2_model.py (add at the very top):

    import mber.patches.nbb2_compat  # noqa: F401  – apply HMMER 3.4 patches

Or from the command line before launching mber-vhh:

    python -c "import mber.patches.nbb2_compat"
"""

import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Monkey-patch anarci to handle HMMER 3.4 returning None for query_start/end.
#
# HMMER 3.4 occasionally produces domain hits where query_start or query_end
# is None. The anarci package (written for HMMER 3.1) does not guard against
# this, causing TypeErrors during sorting and alignment parsing. The patches
# below filter or short-circuit around these corrupt hits without modifying the
# installed anarci package itself.
# ---------------------------------------------------------------------------

try:
    import anarci.anarci as _anarci_module

    # --- Patch _domains_are_same ---
    _original_domains_are_same = _anarci_module._domains_are_same

    def _patched_domains_are_same(d1, d2):
        """Return False if either domain has None query_start/query_end."""
        if (
            getattr(d1, 'query_start', None) is None
            or getattr(d1, 'query_end', None) is None
            or getattr(d2, 'query_start', None) is None
            or getattr(d2, 'query_end', None) is None
        ):
            return False
        return _original_domains_are_same(d1, d2)

    _anarci_module._domains_are_same = _patched_domains_are_same

    # --- Patch _hmm_alignment_to_states ---
    _original_hmm_alignment_to_states = _anarci_module._hmm_alignment_to_states

    def _patched_hmm_alignment_to_states(*args, **kwargs):
        """Return empty result if hsp has None query_start/query_end."""
        # The first positional argument is the hsp object
        hsp = args[0] if args else kwargs.get('hsp')
        if hsp is not None:
            if (
                getattr(hsp, 'query_start', None) is None
                or getattr(hsp, 'query_end', None) is None
            ):
                return ([], [], [])
        return _original_hmm_alignment_to_states(*args, **kwargs)

    _anarci_module._hmm_alignment_to_states = _patched_hmm_alignment_to_states

    # --- Patch _parse_hmmer_query ---
    _original_parse_hmmer_query = _anarci_module._parse_hmmer_query

    def _patched_parse_hmmer_query(query, *args, **kwargs):
        """Filter out individual hsps with None query_start/query_end."""
        if query is not None and hasattr(query, 'hsps'):
            query.hsps = [
                hsp for hsp in query.hsps
                if (
                    getattr(hsp, 'query_start', None) is not None
                    and getattr(hsp, 'query_end', None) is not None
                )
            ]
        return _original_parse_hmmer_query(query, *args, **kwargs)

    _anarci_module._parse_hmmer_query = _patched_parse_hmmer_query

    logger.debug("anarci monkey-patch applied successfully (HMMER 3.4 compat)")

except ImportError:
    logger.debug("anarci not installed; monkey-patch not applied")
except AttributeError as e:
    logger.warning(
        "anarci monkey-patch could not be applied (API may have changed): %s", e
    )

# ---------------------------------------------------------------------------
# Patch ImmuneBuilder's number_sequences to skip anarci when scheme='raw'.
#
# When numbering_scheme='raw' (the NanoBodyBuilder2 default), numbering is a
# no-op (just enumerate). The chain-type assertion in number_sequences calls
# anarci which triggers the HMMER 3.4 / BioPython parser bug. Bypassing it
# entirely for 'raw' is safe because the caller already labels the chain type.
# ---------------------------------------------------------------------------

try:
    import ImmuneBuilder.sequence_checks as _seq_checks_module

    _original_number_sequences = _seq_checks_module.number_sequences

    def _patched_number_sequences(sequences, numbering_scheme, **kwargs):
        """
        When numbering_scheme='raw', skip anarci entirely and return
        simple enumerate-based numbering. This avoids the HMMER 3.4 /
        BioPython parser incompatibility that causes chain recognition
        to fail.
        """
        if numbering_scheme == "raw":
            numbered = {}
            for chain_type, seq in sequences.items():
                numbered[chain_type] = list(enumerate(seq, start=1))
            return numbered
        return _original_number_sequences(sequences, numbering_scheme, **kwargs)

    _seq_checks_module.number_sequences = _patched_number_sequences
    logger.debug("ImmuneBuilder number_sequences patch applied (raw scheme bypass)")
except (ImportError, AttributeError) as e:
    logger.debug("ImmuneBuilder number_sequences patch skipped: %s", e)
