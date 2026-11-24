import glob,os,sys
from PIL import Image,ImageDraw,ImageFont
d=r'D:/PROJECT_work/cams_1er/preview/'
names=sys.argv[1].split(',')
W,H=1617,689; fw=int(H*16/9); x0=(W-fw)//2
tw,th=560,315; cols=3; rows=(len(names)+cols-1)//cols
S=Image.new('RGB',(cols*tw,rows*(th+24)),(20,20,20)); dr=ImageDraw.Draw(S); f=ImageFont.truetype('arialbd.ttf',18)
for i,n in enumerate(names):
    im=Image.open(d+n+'.png').convert('RGB').crop((x0,0,x0+fw,H)).resize((tw,th),Image.LANCZOS)
    x=(i%cols)*tw; y=(i//cols)*(th+24); S.paste(im,(x,y+24)); dr.text((x+6,y+2),n,font=f,fill=(255,140,60))
S.save(sys.argv[2],quality=88); print(S.size)
