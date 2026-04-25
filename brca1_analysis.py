import ssl
ssl._create_default_https_context = ssl._create_unverified_context

from Bio import Entrez, SeqIO

Entrez.email = "yuta.ishikawa2028@gmail.com"

handle = Entrez.efetch(db="nucleotide", id="NM_000546", rettype="fasta")
record = SeqIO.read(handle, "fasta")

print("取得成功！")
print(f"配列名: {record.id}")
print(f"配列長: {len(record.seq)} bp")
print(f"最初の100塩基: {record.seq[:100]}")

import matplotlib.pyplot as plt
import matplotlib
matplotlib.rcParams['font.family'] = 'MS Gothic'  # 日本語対応

# GC含量を計算する関数
def gc_content(seq):
    g = seq.count('G')
    c = seq.count('C')
    return (g + c) / len(seq) * 100

# 全体のGC含量
total_gc = gc_content(str(record.seq))
print(f"\n全体のGC含量: {total_gc:.2f}%")

windows = [50, 100, 300]  # 3種類の粒度で比較

plt.figure(figsize=(12, 8))
for idx, window in enumerate(windows):
    gc_values = []
    positions = []
    for i in range(0, len(record.seq) - window, window):
        chunk = str(record.seq[i:i+window])
        gc_values.append(gc_content(chunk))
        positions.append(i)
    plt.subplot(3, 1, idx + 1)
    plt.plot(positions, gc_values, linewidth=0.8)
    plt.axhline(y=total_gc, color='red', linestyle='--', label=f'平均: {total_gc:.1f}%')
    plt.ylabel('GC含量 (%)')
    plt.title(f'ウィンドウサイズ: {window}bp')
    plt.legend(fontsize=8)

plt.xlabel('塩基の位置 (bp)')
plt.tight_layout()
plt.savefig('gc_window_comparison.png', dpi=150)
plt.show()
print("グラフを gc_window_comparison.png に保存しました。")
# ORF検出します
print("\n--- ORF検出 ---")

def find_orfs(seq, min_length=100):
    orfs = []
    for strand, nuc in [(+1, str(seq)), (-1, str(seq.reverse_complement()))]:
        for frame in range(3):
            i = frame
            while i < len(nuc) - 2:
                if nuc[i:i+3] == 'ATG':
                    for j in range(i, len(nuc) - 2, 3):
                        if nuc[j:j+3] in ('TAA', 'TAG', 'TGA'):
                            length = j - i
                            if length >= min_length:
                                orfs.append({
                                    'start': i,
                                    'end': j + 3,
                                    'length': length,
                                    'strand': strand,
                                    'frame': frame + 1
                                })
                            i = j
                            break
                i += 3

    return sorted(orfs, key=lambda x: x['length'], reverse=True)

orfs = find_orfs(record.seq)
print(f"検出されたORF数: {len(orfs)}")
print(f"\n上位5つのORF:")
for i, orf in enumerate(orfs[:5]):
    strand_str = "+" if orf['strand'] == 1 else "-"
    print(f"  {i+1}. 位置: {orf['start']}-{orf['end']}, 長さ: {orf['length']}bp, 鎖: {strand_str}, フレーム: {orf['frame']}")

# ORFの長さ分布をグラフにしています。
lengths = [o['length'] for o in orfs]
plt.figure(figsize=(10, 5))
plt.hist(lengths, bins=30, color='salmon', edgecolor='black')
plt.xlabel('ORFの長さ (bp)')
plt.ylabel('個数')
plt.title('TP53 ORF長さ分布')
plt.tight_layout()
plt.savefig('orf_distribution.png', dpi=150)
plt.show()
print("グラフを orf_distribution.png に保存しました。")