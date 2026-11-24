"""Read-only analytics and deterministic SOP comparisons over authorized documents."""
import difflib
import hashlib
import re
from collections import Counter
from pathlib import Path
from sqlalchemy import func, select
from app.models.document import AuditLog, Document
from app.rag.loaders import load_file


def document_analytics(db, departments: set[str], admin: bool = False) -> dict:
    docs = db.scalars(select(Document).where(Document.department.in_(departments))).all()
    status_counts = Counter(d.status for d in docs)
    department_counts = Counter(d.department for d in docs if d.status == 'active')
    kind_counts = Counter(d.doc_type for d in docs if d.status == 'active')
    result = {
        'total_versions': len(docs), 'active_documents': status_counts['active'],
        'superseded_versions': status_counts['superseded'],
        'by_department': dict(sorted(department_counts.items())),
        'by_type': dict(sorted(kind_counts.items())),
    }
    if admin:
        # Avoid emitting questions, raw audit details, credentials or protected names.
        actions = db.execute(select(AuditLog.action, func.count(AuditLog.id)).group_by(AuditLog.action)).all()
        result['audit_action_counts'] = dict(actions)
    return result


def compare_versions(db, first_id: int, second_id: int, departments: set[str], max_lines: int = 90) -> dict:
    ids = {first_id, second_id}
    if len(ids) != 2:
        raise ValueError('Choose two different document versions')
    docs = db.scalars(select(Document).where(Document.id.in_(ids), Document.department.in_(departments))).all()
    if len(docs) != 2:
        raise LookupError('Documents not found or inaccessible')
    a, b = sorted(docs, key=lambda d: d.version)
    if a.filename != b.filename or a.department != b.department:
        raise ValueError('Versions must belong to the same filename and department')
    def get_lines(doc):
        stored = Path(doc.storage_path)
        if not stored.is_file():
            raise FileNotFoundError('Document source is unavailable on this server')
        return '\n'.join(page['text'] for page in load_file(str(stored))).splitlines()
    earlier, later = get_lines(a), get_lines(b)
    changes = list(difflib.unified_diff(earlier, later, fromfile=f'{a.filename} v{a.version}', tofile=f'{b.filename} v{b.version}', lineterm=''))
    return {
        'filename': a.filename, 'department': a.department,
        'earlier_id': a.id, 'earlier_version': a.version,
        'later_id': b.id, 'later_version': b.version,
        'changed': bool(changes), 'diff_lines': changes[:max_lines],
        'truncated': len(changes) > max_lines,
        'note': 'Textual comparison only. Requires human QA review; not a regulatory approval.'
    }


def evidence_gap_analysis(question: str, passages: list[dict]) -> dict:
    """Transparent lexical checklist, not a validated compliance verdict."""
    from app.rag.retrieval import terms
    clauses = [c.strip() for c in re.split(r'[,;\n]+', question) if len(terms(c)) >= 2][:12]
    if not clauses:
        raise ValueError('Provide checklist requirements separated by commas or semicolons')
    results = []
    for clause in clauses:
        query_terms = set(terms(clause))
        matches = []
        for i, p in enumerate(passages, 1):
            overlap = len(query_terms.intersection(terms(p['text']))) / max(len(query_terms), 1)
            if overlap >= 0.6:
                matches.append({'label': f'S{i}', 'filename': p['metadata'].get('filename'),
                                'page': p['metadata'].get('page'), 'overlap': round(overlap, 2)})
        results.append({'requirement': clause, 'evidence_found': bool(matches), 'sources': matches[:3]})
    return {'checks': results, 'with_potential_evidence': sum(x['evidence_found'] for x in results),
            'total_checks': len(results),
            'disclaimer': 'Keyword overlap is not proof of compliance. Review the source documents manually.'}


def route_query(question: str) -> str:
    """Simple, inspectable QA/regulatory/document routing (no unverified agent claims)."""
    value = question.lower()
    if re.search(r'\b(oos|deviation|batch|release|quality|capa|cleaning)\b', value):
        return 'quality_agent'
    if re.search(r'\b(regulator|regulatory|ich|fda|gmp|submission|compliance)\b', value):
        return 'regulatory_agent'
    return 'document_agent'
