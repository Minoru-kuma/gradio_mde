"""Validate load-time capability declarations without importing a model framework."""
import json

from .contracts import normalize_outputs


def check_runtime_capabilities(capabilities, requested_outputs, *, view_count=1):
    """Return a JSON snapshot and warnings; reject unavailable outputs before predict.

    Empty maps preserve single-view adapters that predate runtime declarations. Once an adapter
    provides a nonempty map, every requested output must be explicitly declared.
    Conditional descriptions are provenance, not expressions evaluated by core.
    Output presence and numeric validation still run after prediction.
    """
    requested = normalize_outputs(requested_outputs)
    if type(view_count) is not int or view_count < 1:
        raise ValueError('Input view count must be a positive integer')
    if not isinstance(capabilities, dict):
        raise ValueError('Runtime capabilities must be a JSON object')
    for name, capability in capabilities.items():
        if (not isinstance(name, str) or not name or not isinstance(capability, dict)
                or capability.get('status') not in ('supported', 'conditional', 'unsupported')
                or ('condition' in capability and not isinstance(capability['condition'], str))):
            raise ValueError(f'Invalid runtime capability declaration: {name!r}')
    try:
        snapshot = json.loads(json.dumps(capabilities, allow_nan=False))
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError('Runtime capabilities must contain finite JSON metadata') from error
    warnings = []
    if view_count > 1 and snapshot.get('multi_view', {}).get('status') not in ('supported', 'conditional'):
        raise ValueError('Explicit runtime multi_view capability is required for multiple views')
    if not snapshot:
        warnings.append('Runtime capabilities undeclared by legacy adapter; requested outputs will be validated after predict')
    else:
        for name in requested:
            if name not in snapshot:
                raise ValueError(f'Missing requested runtime capability: {name}')
            status = snapshot[name]['status']
            if status == 'unsupported':
                raise ValueError(f'Unsupported requested runtime capability: {name}')
            if status == 'conditional':
                warnings.append(f'Runtime capability {name} is conditional; requested output will be validated after predict')
    check = {'declaration': 'declared' if snapshot else 'legacy_undeclared',
             'requested_outputs': requested, 'capabilities': snapshot}
    if view_count > 1:
        check['input_view_count'] = view_count
    return check, warnings
