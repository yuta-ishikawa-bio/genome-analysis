import ssl
ssl._create_default_https_context = ssl._create_unverified_context

from Bio import Entrez, SeqIO
import matplotlib.pyplot as plt
import matplotlib
matplotlib.rcParams['font.family'] = 'MS Gothic'

Entrez.email = "yuta.ishikawa2028@gmail.com"

# 解析する遺伝子リスト
genes = {
    "BRCA1": "NM_007294",
    "TP53": "NM_000546"
}

records = {}
for name, gene_id in genes.items():
    handle = Entrez.efetch(db="nucleotide", id=gene_id, rettype="fasta")
    records[name] = SeqIO.read(handle, "fasta")
    print(f"{name} 取得成功！ 配列長: {len(records[name].seq)} bp")

# GC含量を計算する関数
def gc_content(seq):
    g = seq.count('G')
    c = seq.count('C')
    return (g + c) / len(seq) * 100

# BRCA1とTP53を同じグラフで比較
window = 100
plt.figure(figsize=(12, 5))

colors = {"BRCA1": "steelblue", "TP53": "salmon"}
for name, record in records.items():
    gc_values = []
    positions = []
    for i in range(0, len(record.seq) - window, window):
        chunk = str(record.seq[i:i+window])
        gc_values.append(gc_content(chunk))
        positions.append(i)
    total_gc = gc_content(str(record.seq))
    plt.plot(positions, gc_values, color=colors[name], linewidth=0.8, label=f"{name} (平均: {total_gc:.1f}%)")

plt.xlabel('塩基の位置 (bp)')
plt.ylabel('GC含量 (%)')
plt.title('BRCA1 vs TP53 GC含量比較')
plt.legend()
plt.tight_layout()
plt.savefig('comparison.png', dpi=150)
plt.show()
print("グラフを comparison.png に保存しました！")