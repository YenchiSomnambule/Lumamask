from PIL import Image, ImageDraw
import os
ORANGE=(217,119,87,255); LIGHT=(250,249,245,255)
def lerp(a,b,t): return tuple(int(a[i]+(b[i]-a[i])*t) for i in range(4))
FADE=lerp(ORANGE,LIGHT,0.55)
def render(size):
    S=size*4
    img=Image.new("RGBA",(S,S),(0,0,0,0)); d=ImageDraw.Draw(img)
    sc=lambda v:v*S/256
    pts=[(40,62),(128,20),(216,62),(216,130),(210,160),(192,196),(160,222),(128,242),(96,222),(64,196),(46,160),(40,130)]
    d.polygon([(sc(x),sc(y)) for x,y in pts], fill=ORANGE)
    def rr(x,y,w,h,col): d.rounded_rectangle([sc(x),sc(y),sc(x+w),sc(y+h)], radius=sc(h/2), fill=col)
    rr(78,100,100,18,FADE); rr(78,128,100,21,LIGHT); rr(78,159,69,18,FADE)
    return img.resize((size,size), Image.LANCZOS)
sizes=[16,32,48,64,128,256]
imgs=[render(s) for s in sizes]
here=os.path.dirname(os.path.abspath(__file__))
path=os.path.join(here,"Lumamask.ico")
imgs[-1].save(path, format="ICO", sizes=[(s,s) for s in sizes], append_images=imgs[:-1])
print("ICO written to", path)