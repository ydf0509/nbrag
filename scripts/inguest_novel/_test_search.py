import sys
sys.path.insert(0, 'd:/codes/nbrag')
import my_load_config  # noqa
from nbrag.core import search

documents, metadatas, distances, rerank_used, total, rerank_scores = search(
    '太阳熄灭后地球发生了什么变化',
    collection_name='doomsday_sun',
    top_k=5,
    use_rerank=True,
)

print(f'total chunks: {total}')
print(f'rerank used: {rerank_used}')
print(f'results: {len(documents)}')
print()

for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances), 1):
    print(f'--- Result {i} ---')
    print(f"Source: {meta.get('source', '')}")
    print(f"Lines: {meta.get('line_start', '')}-{meta.get('line_end', '')}")
    print(f"Distance: {dist:.4f}")
    print(f"Text: {doc[:500]}...")
    print()
