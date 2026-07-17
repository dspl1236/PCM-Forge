# Carve PCM3Root (SH4 ELF) out of a decompressed PCM3.1 IFS1 raw image.
# Usage: python carve_pcm3root.py <raw_ifs> <out_pcm3root>
import struct, sys
raw=sys.argv[1]; out=sys.argv[2]
d=open(raw,'rb').read()
def elf_size(pos):
    # stripped SH4 ELF -> size = max(p_offset+p_filesz) over PT_LOAD program headers
    e_phoff=struct.unpack_from('<I',d,pos+0x1c)[0]
    e_phentsize,e_phnum=struct.unpack_from('<HH',d,pos+0x2a)
    end=0
    for i in range(e_phnum):
        o=pos+e_phoff+i*e_phentsize
        if o+20>len(d): return 0
        p_off,p_vaddr,p_paddr,p_filesz=struct.unpack_from('<IIII',d,o+4)
        end=max(end,p_off+p_filesz)
    return end
# find all SH4 (machine 0x2A) LE ELFs
elfs=[]; pos=0
while True:
    pos=d.find(b'\x7fELF\x01\x01\x01',pos)
    if pos<0: break
    if struct.unpack_from('<H',d,pos+18)[0]==0x2A:
        elfs.append((pos,elf_size(pos)))
    pos+=4
print('SH4 ELFs found: %d'%len(elfs))
for p,s in sorted(elfs,key=lambda x:-x[1])[:6]:
    print('  @0x%08x  size=%d (%.2f MB)'%(p,s,s/1e6))
# PCM3Root = the ELF whose body contains the CPSoundPresCtrl / audio strings + is big (~6.5MB)
cand=None
for p,s in elfs:
    if s<2_000_000: continue
    body=d[p:p+s]
    if b'CPSoundPresCtrl' in body and b'Fallback from A2DP to TUNER_FM' in body:
        cand=(p,s); break
if not cand:
    # fallback: largest ELF
    cand=max(elfs,key=lambda x:x[1])
    print('WARN: string-match failed, using largest ELF')
p,s=cand
open(out,'wb').write(d[p:p+s])
print('CARVED PCM3Root @0x%08x size=%d -> %s'%(p,s,out))
# quick verify
body=d[p:p+s]
for tag in (b'CPSoundPresCtrl',b'CAudioMngPersistence',b'Fallback from A2DP to TUNER_FM',b'KeyInput.SPHKeyInput'):
    print('  has %-32s %s'%(tag.decode(), tag in body))
