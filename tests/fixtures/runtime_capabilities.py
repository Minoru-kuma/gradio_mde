"""Load-time declarations independent of any real model or checkpoint."""
from tests.fixtures.geometry import GeometryAdapter


class RuntimeCapabilityAdapter(GeometryAdapter):
    def load(self, context):
        loaded = super().load(context)
        mode = context.variant['runtime_fixture']
        loaded.capabilities = {'depth': {'status': 'supported'}, 'points': {'status': 'supported'}}
        if mode == 'unsupported':
            loaded.capabilities['points']['status'] = 'unsupported'
        elif mode == 'missing':
            del loaded.capabilities['points']
        elif mode == 'invalid':
            loaded.capabilities['points']['status'] = True
        elif mode == 'nonjson':
            loaded.capabilities['depth']['bad_extension'] = object()
        elif mode == 'conditional':
            loaded.capabilities['points'].update(status='conditional', condition='fixture output must exist')
        elif mode == 'legacy':
            loaded.capabilities = {}
        return loaded
