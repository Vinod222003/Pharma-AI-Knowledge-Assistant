"""Lightweight offline regression metrics; does not claim clinical/GxP validity."""
import re


def evaluate_case(actual: dict, expected_source: str | None = None, expected_insufficient: bool | None = None) -> dict:
    labels = {s.get('label') for s in actual.get('sources', [])}
    cited = set(re.findall(r'\[([Ss]\d+)\]', actual.get('answer', '')))
    result = {'citations_resolve': bool(cited) and cited.issubset(labels),
              'source_count': len(actual.get('sources', [])),
              'insufficient_evidence': bool(actual.get('insufficient_evidence'))}
    if expected_source is not None:
        result['expected_source_found'] = any(x.get('filename') == expected_source for x in actual.get('sources', []))
    if expected_insufficient is not None:
        result['evidence_flag_correct'] = result['insufficient_evidence'] == expected_insufficient
    return result
