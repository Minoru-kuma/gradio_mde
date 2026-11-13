"""Provider-neutral camera task configuration; numeric/model imports stay out."""
import hashlib
from pathlib import Path
import uuid

from .environments import EnvironmentProfile
from .storage import contained_path, read_json, sha256_file, write_json


class CameraEstimator:
    def __init__(self, backend, project_root, config_path):
        self.backend,self.root=backend,Path(project_root).resolve()
        path=Path(config_path).resolve();data=read_json(path)
        if (data.get('schema_version')!='1.0' or set(data)-{'schema_version','definition_ref','environment','checkpoint','timeout_seconds'}):
            raise ValueError('Invalid camera estimator target configuration')
        self.definition=contained_path(self.root,data['definition_ref'])
        self.task=read_json(self.definition)
        if self.task.get('task_kind')!='pinhole-camera-v1' or self.task.get('schema_version')!='1.0':
            raise ValueError('Unsupported camera task kind')
        self.environment={**self.task['environment_ref']}
        self.environment['definition_digest']=sha256_file(contained_path(self.root,self.environment['definition_ref']))
        profile=data['environment']
        if set(profile) not in ({'name'},{'prefix'}):raise ValueError('Configure one camera task environment name or prefix')
        prefix=str((path.parent/profile['prefix']).resolve()) if 'prefix' in profile else None
        if backend.manager is None:raise ValueError('Camera estimator requires an execution backend manager')
        env_id=self.environment['environment_id']
        if env_id in backend.manager.resolver.profiles:raise ValueError('Camera environment ID is already configured')
        backend.manager.resolver.profiles[env_id]=EnvironmentProfile(env_id,name=profile.get('name'),prefix=prefix)
        backend.manager.resolver.resolve(self.environment)
        self.checkpoint=(path.parent/data['checkpoint']).resolve()
        self.timeout=data.get('timeout_seconds',180)
        if type(self.timeout) is not int or self.timeout<1:raise ValueError('Camera timeout must be positive integer')

    def identity(self):
        expected=self.task['checkpoint']
        if (not self.checkpoint.is_file() or self.checkpoint.stat().st_size!=expected['size_bytes']
                or sha256_file(self.checkpoint)!=expected['sha256']):
            raise ValueError('Camera estimator checkpoint is unprepared or checksum mismatched')
        digest=hashlib.sha256()
        for directory in (self.root/'src',self.definition.parent):
            for p in sorted(directory.rglob('*')):
                if p.is_file() and p.suffix in ('.py','.json','.yml'):
                    digest.update(p.relative_to(self.root).as_posix().encode());digest.update(p.read_bytes())
        return {'task':self.task,'definition_sha256':sha256_file(self.definition),'source_digest':digest.hexdigest(),
                'environment':self.environment,'device':'cpu','dtype':'float32','seed':0}

    def estimate(self,image_path):
        identity=self.identity()
        work=self.root/'.local/auxiliary-tasks'/uuid.uuid4().hex
        work.mkdir(parents=True)
        request={**identity,'schema_version':'1.0','entrypoint':self.task['entrypoint'],
                 'checkpoint_path':str(self.checkpoint),'image_path':str(Path(image_path).resolve()),
                 'image_sha256':sha256_file(image_path)}
        request_path=work/'request.json';result_path=work/'result.json'
        write_json(request_path,request)
        result=self.backend.execute_task(self.environment,request_path,result_path,work,timeout_seconds=self.timeout)
        if self.identity()!=identity:raise ValueError('Camera provider changed during calibration')
        return result
