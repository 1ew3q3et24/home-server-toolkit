
import zlib, struct, os, math

def png(path, w, h, rgba):
    raw = bytearray()
    stride = w*4
    for y in range(h):
        raw.append(0)
        raw.extend(rgba[y*stride:(y+1)*stride])
    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t+d) & 0xffffffff)
    data = b"\x89PNG\r\n\x1a\n"
    data += chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
    data += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    data += chunk(b"IEND", b"")
    open(path,"wb").write(data)

def lerp(a,b,t): return a+(b-a)*t

def rr(x,y,x0,y0,x1,y1,r):
    cx = min(max(x,x0+r), x1-r); cy = min(max(y,y0+r), y1-r)
    dx=x-cx; dy=y-cy
    return dx*dx+dy*dy <= r*r

def circ(x,y,cx,cy,r):
    return (x-cx)**2+(y-cy)**2 <= r*r

def render(size, mode, ss=2):
    # mode: 'legacy' | 'bg' | 'fg'
    W=size; out=bytearray(W*W*4)
    inv = 1.0/W
    for py in range(W):
        for px in range(W):
            ar=ag=ab=aa=0.0
            for sy in range(ss):
                for sx in range(ss):
                    x=(px+ (sx+0.5)/ss)*inv
                    y=(py+ (sy+0.5)/ss)*inv
                    # background
                    if mode != 'fg':
                        if mode=='legacy':
                            inbg = rr(x,y,0.015,0.015,0.985,0.985,0.20)
                        else:
                            inbg = True
                    else:
                        inbg = False
                    if inbg:
                        t=max(0.0,min(1.0,y))
                        r0,g0,b0 = lerp(59,67,t), lerp(130,56,t), lerp(246,202,t)
                        ar+=r0; ag+=g0; ab+=b0; aa+=255
                        # gamepad white
                        body = rr(x,y,0.17,0.395,0.83,0.665,0.135)
                        grip = circ(x,y,0.275,0.575,0.135) or circ(x,y,0.725,0.575,0.135)
                        if body or grip:
                            ar-=r0; ag-=g0; ab-=b0; ar+=255; ag+=255; ab+=255
                            # details
                            d = (rr(x,y,0.295,0.505,0.435,0.560,0.010) or
                                 rr(x,y,0.335,0.465,0.395,0.600,0.010) or
                                 circ(x,y,0.615,0.485,0.030) or
                                 circ(x,y,0.675,0.485,0.030) or
                                 circ(x,y,0.645,0.455,0.030) or
                                 circ(x,y,0.645,0.515,0.030))
                            if d:
                                ar-=255; ag-=255; ab-=255
                                ar+=37; ag+=99; ab+=235
                    elif mode=='fg':
                        # transparent background, white gamepad with padding (safe zone)
                        body = rr(x,y,0.235,0.430,0.765,0.645,0.115)
                        grip = circ(x,y,0.315,0.545,0.115) or circ(x,y,0.685,0.545,0.115)
                        if body or grip:
                            ar+=255; ag+=255; ab+=255; aa+=255
                            d = (rr(x,y,0.335,0.505,0.445,0.548,0.008) or
                                 rr(x,y,0.365,0.472,0.415,0.582,0.008) or
                                 circ(x,y,0.585,0.500,0.026) or
                                 circ(x,y,0.635,0.500,0.026) or
                                 circ(x,y,0.610,0.475,0.026) or
                                 circ(x,y,0.610,0.525,0.026))
                            if d:
                                ar-=255; ag-=255; ab-=255
                                ar+=37; ag+=99; ab+=235
            n=ss*ss
            i=(py*W+px)*4
            out[i]=max(0,min(255,int(ar/n+0.5)))
            out[i+1]=max(0,min(255,int(ag/n+0.5)))
            out[i+2]=max(0,min(255,int(ab/n+0.5)))
            out[i+3]=max(0,min(255,int(aa/n+0.5)))
    return out

def down(src, S, D):
    out=bytearray(D*D*4)
    for y in range(D):
        y0=int(y*S/D); y1=max(y0+1,int((y+1)*S/D))
        for x in range(D):
            x0=int(x*S/D); x1=max(x0+1,int((x+1)*S/D))
            r=g=b=a=0; n=0
            for yy in range(y0,y1):
                base=yy*S*4
                for xx in range(x0,x1):
                    i=base+xx*4
                    r+=src[i]; g+=src[i+1]; b+=src[i+2]; a+=src[i+3]; n+=1
            i=(y*D+x)*4
            out[i]=r//n; out[i+1]=g//n; out[i+2]=b//n; out[i+3]=a//n
    return out

root="/home/lzj/apk/src/res"
dens = [("mdpi",1.0),("hdpi",1.5),("xhdpi",2.0),("xxhdpi",3.0),("xxxhdpi",4.0)]

legacy = render(192,"legacy",3)
bg = render(432,"bg",2)
fg = render(432,"fg",3)

for name,scale in dens:
    d=os.path.join(root,"mipmap-"+name); os.makedirs(d,exist_ok=True)
    ls=int(48*scale); bs=int(108*scale); fs=int(108*scale)
    png(os.path.join(d,"ic_launcher.png"), ls, ls, legacy if ls==192 else down(legacy,192,ls))
    png(os.path.join(d,"ic_launcher_bg.png"), bs, bs, bg if bs==432 else down(bg,432,bs))
    png(os.path.join(d,"ic_launcher_fg.png"), fs, fs, fg if fs==432 else down(fg,432,fs))
    print(name, ls, bs, fs)
os.makedirs(os.path.join(root,"mipmap-anydpi-v26"),exist_ok=True)
print("ok")
