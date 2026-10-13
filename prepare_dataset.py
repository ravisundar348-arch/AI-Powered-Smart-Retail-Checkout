from pathlib import Path
import random, shutil
root=Path(__file__).resolve().parent
src=root/'Dataset'/'Cake'/'final_project_images'
out=root/'Aug_Dataset'
ext={'.jpg','.jpeg','.png','.webp','.bmp'}
if not src.is_dir(): raise SystemExit(f'Source not found: {src}')
classes=sorted(p for p in src.iterdir() if p.is_dir())
if len(classes)!=8: raise SystemExit(f'Expected 8 classes, found {len(classes)}')
if out.exists(): raise SystemExit('Aug_Dataset already exists; inspect it first.')
random.seed(42)
plan={}
for folder in classes:
    images=sorted(p for p in folder.rglob('*') if p.is_file() and p.suffix.lower() in ext)
    random.shuffle(images)
    n=len(images)
    if n<5: raise SystemExit(f'Not enough images: {folder.name} ({n})')
    nt=max(1,round(n*.15)); nv=max(1,round(n*.15)); end=n-nt-nv
    plan[folder.name]={'Train':images[:end],'Val':images[end:n-nt],'Test':images[n-nt:]}
try:
    for name,splits in plan.items():
        for split,images in splits.items():
            dest=out/split/name; dest.mkdir(parents=True,exist_ok=True)
            for i,image in enumerate(images): shutil.copy2(image,dest/f'{i:04d}{image.suffix.lower()}')
    print('Dataset prepared successfully!')
    for name,splits in plan.items(): print(name,{k:len(v) for k,v in splits.items()})
except Exception:
    shutil.rmtree(out,ignore_errors=True)
    raise
