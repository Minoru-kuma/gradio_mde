"""Local target metadata: logical environments and per-variant checkpoint locations."""
from dataclasses import dataclass, field
from pathlib import Path
import re

from .contracts import check_schema
from .environments import EnvironmentProfile, EnvironmentResolver
from .storage import read_json


@dataclass
class TargetConfiguration:
    profiles: dict[str, EnvironmentProfile] = field(default_factory=dict)
    checkpoints: dict[str, Path] = field(default_factory=dict)
    cached_checkpoints: set[str] = field(default_factory=set)

    @classmethod
    def read(cls, path):
        path = Path(path).resolve()
        data = read_json(path)
        check_schema(data)
        if data.keys() - {'schema_version', 'environments', 'checkpoints'}:
            raise ValueError('Unknown target configuration field')
        profiles, checkpoints = {}, {}
        if not isinstance(data.get('environments', {}), dict) or not isinstance(data.get('checkpoints', {}), dict):
            raise ValueError('Target environments / checkpoints must be objects')
        def location(value):
            if not isinstance(value, str) or not value:
                raise ValueError('Target path must be a nonempty string')
            return (path.parent / value).resolve()
        for key, value in data.get('environments', {}).items():
            if (not re.fullmatch(r'[a-z0-9][a-z0-9_-]*', key) or not isinstance(value, dict)
                    or value.keys() - {'name', 'prefix'}):
                raise ValueError('Invalid target environment profile')
            if set(value) not in ({'name'}, {'prefix'}):
                raise ValueError('Configure exactly one Conda name or prefix')
            if 'name' in value and (not isinstance(value['name'], str) or not value['name'] or value['name'] == 'base'):
                raise ValueError('Invalid independent Conda name')
            profiles[key] = EnvironmentProfile(key, name=value.get('name'),
                prefix=str(location(value['prefix'])) if 'prefix' in value else None)
        for key, value in data.get('checkpoints', {}).items():
            if not re.fullmatch(r'[a-z0-9][a-z0-9_-]*/[a-z0-9][a-z0-9_-]*', key):
                raise ValueError('Checkpoint key must be model_id/variant_id')
            checkpoints[key] = location(value)
        return cls(profiles, checkpoints)

    def preparation(self, info, variant_id, environment_id=None):
        variant = info.effective_variant(variant_id)
        try:
            reference = info.environment(variant_id, environment_id)
            profile = EnvironmentResolver(self.profiles).resolve(reference)
            if profile.prefix and not (Path(profile.prefix) / 'bin/python').is_file():
                raise ValueError('Model environment is not prepared at the configured prefix')
            key = f'{info.model_id}/{variant["variant_id"]}'
            if variant.get('checkpoint') is not None:
                if ((key not in self.checkpoints and key not in self.cached_checkpoints) or
                        (key in self.checkpoints and not self.checkpoints[key].exists())):
                    raise ValueError('Local checkpoint is not prepared for this model / variant')
        except ValueError as error:
            return {'available': False, 'message': f'未準備 / Unprepared: {error}'}
        return {'available': True, 'message': 'Target configured; worker verifies dependencies, source and checkpoint digests.'}
