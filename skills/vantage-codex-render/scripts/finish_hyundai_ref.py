# Final copies for _RESULTS_FINAL: brand marks removed, logo in Hyundai Blue, warm or dim outliers brought in line. Originals in the view folders stay as Codex made them.
import glob,math,os
import cv2
import numpy as np
from PIL import Image,ImageDraw,ImageFont
O=r'D:/BAAK_CHARGUIA/RENDU_A_TRAITE_PROMPTS';R=O+'/_RESULTS_FINAL';V=O+'/_REVIEW';os.makedirs(R,exist_ok=True)
MARKS={'HYPERREAL_1_ARCH_15_DIRECTOR_D02':(1018,770,1054,808),'HYPERREAL_1_ARCH_20_SECRETARY':(449,776,477,810),'HYPERREAL_1_ARCH_18_TEAM_OFFICE':(368,492,395,531)}
BLUE={'HYPERREAL_1_ARCH_05_RECEPTION_DESK':(.36,.12,.60,.46),'DETAIL_2_1_ARCH_05_RECEPTION_DESK':(.25,0,.60,.75)}
NAVY=np.array([0,0x2C,0x5F],float)
def rb(a):
    l=a.mean(2);m=(l>40)&(l<235);return a[...,0][m].mean()/max(a[...,2][m].mean(),1)
def p99(a):return np.percentile(a.mean(2),99)
def wb(a,k):
    s=math.sqrt(k);a=a.copy();a[...,0]/=s;a[...,2]*=s;return a
def lift(a,g):
    y=a*g;k=235.;over=y>k;y[over]=k+20*(1-np.exp(-(y[over]-k)/20));return y
def retouch(a,key):
    if key in MARKS:
        x0,y0,x1,y1=MARKS[key];m=np.zeros(a.shape[:2],np.uint8);m[y0:y1,x0:x1]=255
        a=cv2.inpaint(np.clip(a,0,255).astype(np.uint8),m,5,cv2.INPAINT_TELEA).astype(float)
    if key in BLUE:
        h,w,_=a.shape;x0,y0,x1,y1=BLUE[key];b=np.zeros((h,w));b[int(y0*h):int(y1*h),int(x0*w):int(x1*w)]=1
        d=(a[...,2]-a[...,0])*b;ref=np.median(d[d>60]);al=np.clip(d/ref,0,1)[...,None];a=a*(1-al)+NAVY*al
    return a
def save(a,key):
    Image.fromarray(np.clip(a,0,255).astype(np.uint8)).save(f'{R}/{key}.png')
names=[os.path.basename(d) for d in sorted(glob.glob(O+'/1_*')) if os.path.exists(d+'/PROMPT_HYPER.txt')]
log=[]
for n in names:
    d=f'{O}/{n}';key=f'HYPERREAL_{n}';a=retouch(np.asarray(Image.open(f'{d}/{key}.png').convert('RGB'),float),key)
    r0=rb(a);p0=p99(a)
    if r0>1.50:a=wb(a,r0/1.45)
    if p0<212:a=lift(a,min(222/p0,1.18))
    h=rb(a);save(a,key)
    if r0>1.50 or p0<212:log.append(f'{n[2:]} main R/B {r0:.2f}->{h:.2f} p99 {p0:.0f}->{p99(a):.0f}')
    for j in (1,2):
        key=f'DETAIL_{j}_{n}';c=retouch(np.asarray(Image.open(f'{d}/{key}.png').convert('RGB'),float),key)
        r1=rb(c);p1=p99(c);ch=False
        if r1>max(h+.15,1.5):c=wb(c,r1/max(h+.10,1.45));ch=True
        if p1<195:c=lift(c,min(210/p1,1.18));ch=True
        save(c,key)
        if ch:log.append(f'{n[2:]} close {j} R/B {r1:.2f}->{rb(c):.2f} p99 {p1:.0f}->{p99(c):.0f}')
print('\n'.join(log));print('adjusted',len(log))
F=ImageFont.truetype('arial.ttf',14)
def sheet(items,cols,w,out):
    h=int(w*9/16);rows=(len(items)+cols-1)//cols;S=Image.new('RGB',(cols*w,rows*h),(25,25,25));
    for i,(p,t) in enumerate(items):
        im=Image.open(p).convert('RGB').resize((w,h),Image.LANCZOS);x=(i%cols)*w;y=(i//cols)*h;S.paste(im,(x,y));dr=ImageDraw.Draw(S);dr.rectangle((x,y,x+8+dr.textlength(t,font=F),y+18),fill=(0,0,0));dr.text((x+4,y+1),t,font=F,fill=(255,255,255))
    S.save(out,quality=88);print(out,S.size)
sheet([(f'{R}/HYPERREAL_{n}.png',f'{i+1} {n[2:][:30]}') for i,n in enumerate(names)],5,384,V+'/FINAL_37_MAIN.jpg')
sheet([(f'{R}/DETAIL_{j}_{n}.png',f'{i+1}.{j}') for i,n in enumerate(names) for j in (1,2)],8,240,V+'/FINAL_74_CLOSEUPS.jpg')
print(len(glob.glob(R+'/*.png')),'files in results')
T=Image.new('RGB',(1200,400));
for i,(n,b) in enumerate((('1_ARCH_15_DIRECTOR_D02',(960,710,1110,860)),('1_ARCH_20_SECRETARY',(388,718,538,868)),('1_ARCH_18_TEAM_OFFICE',(304,414,454,564)))):
    T.paste(Image.open(f'{R}/HYPERREAL_{n}.png').crop(b).resize((400,400),Image.LANCZOS),(i*400,0))
T.save(V+'/logos_after.jpg',quality=90)
