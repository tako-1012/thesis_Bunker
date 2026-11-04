"""Download the pinned public ROS image into temporary storage and flatten its layers."""
import hashlib,json,os,shutil,tarfile,time,urllib.request
from pathlib import Path,PurePosixPath

STORE=Path('/tmp/task019-oci')
ROOT=STORE/'rootfs'
ROOT.mkdir(parents=True,exist_ok=True)
manifest=json.loads((STORE/'manifest.json').read_text())

def token():
    url='https://auth.docker.io/token?service=registry.docker.io&scope=repository:osrf/ros:pull'
    return json.load(urllib.request.urlopen(url,timeout=60))['token']

def safe(path):
    path=Path(path)
    if not path.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError('image path escapes temporary root: '+str(path))
    return path

def member_path(name):
    parts=PurePosixPath(name.lstrip('/')).parts
    if '..' in parts:raise ValueError('parent path in image')
    return ROOT.joinpath(*parts)

def remove(path):
    safe(path.parent)
    if path.is_symlink() or path.is_file():path.unlink()
    elif path.is_dir():shutil.rmtree(path)

def flatten(archive):
    with tarfile.open(archive,'r:*') as tar:
        members=tar.getmembers()
        # Apply whiteouts before the upper layer's ordinary entries.
        for entry in members:
            path=member_path(entry.name)
            if path.name=='.wh..wh..opq':
                directory=safe(path.parent)
                if directory.is_dir():
                    for item in directory.iterdir():remove(item)
            elif path.name.startswith('.wh.'):
                remove(path.with_name(path.name[4:]))
        links=[]
        for entry in members:
            path=member_path(entry.name)
            if path.name.startswith('.wh.'):continue
            safe(path.parent);path.parent.mkdir(parents=True,exist_ok=True)
            if entry.isdir():
                if path.is_symlink() or (path.exists() and not path.is_dir()):remove(path)
                path.mkdir(exist_ok=True)
                path.chmod(entry.mode & 0o1777)
            elif entry.issym():
                remove(path)
                if entry.linkname.startswith('/'):
                    target=member_path(entry.linkname)
                    link=os.path.relpath(target,path.parent)
                else:link=entry.linkname
                if not (path.parent/link).resolve().is_relative_to(ROOT.resolve()):
                    raise ValueError('image symlink escapes temporary root')
                path.symlink_to(link)
            elif entry.islnk():
                remove(path);links.append((path,member_path(entry.linkname)))
            elif entry.isfile():
                remove(path)
                with tar.extractfile(entry) as source,path.open('wb') as target:
                    shutil.copyfileobj(source,target,1024*1024)
                path.chmod(entry.mode & 0o1777)
            elif entry.ischr() or entry.isblk() or entry.isfifo():
                # /dev is bound from the host only inside the isolated namespace.
                continue
            else:raise ValueError('unsupported image entry '+entry.name)
        for path,target in links:os.link(safe(target),path,follow_symlinks=False)

for index,layer in enumerate(manifest['layers'],1):
    digest=layer['digest'].split(':',1)[1]
    archive=STORE/(digest+'.tar.gz')
    done=STORE/(digest+'.applied')
    if done.exists():print('layer',index,'already applied',flush=True);continue
    if not archive.exists():
        req=urllib.request.Request('https://registry-1.docker.io/v2/osrf/ros/blobs/sha256:'+digest,
                                  headers={'Authorization':'Bearer '+token()})
        partial=archive.with_suffix('.part')
        with urllib.request.urlopen(req,timeout=120) as source,partial.open('wb') as target:
            shutil.copyfileobj(source,target,1024*1024)
        assert partial.stat().st_size==layer['size']
        with partial.open('rb') as source:actual=hashlib.file_digest(source,'sha256').hexdigest()
        if actual!=digest:raise ValueError('layer digest mismatch')
        partial.rename(archive)
    else:
        with archive.open('rb') as source:actual=hashlib.file_digest(source,'sha256').hexdigest()
        if actual!=digest:raise ValueError('cached layer digest mismatch')
    print('extracting verified layer',index,'/',len(manifest['layers']),'compressed_bytes',archive.stat().st_size,flush=True)
    flatten(archive)
    done.write_text(digest+'\n')
print('all image layers verified and extracted:',ROOT,flush=True)
