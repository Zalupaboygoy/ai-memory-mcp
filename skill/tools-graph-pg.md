# Tools: Graph

Exact argument names:

```
link_entries(from_entry_id, to_entry_id, relation_type, description?)
unlink_entries(from_entry_id, to_entry_id, relation_type?)
get_related(entry_id, relation_type?, direction="both")   # direction: incoming | outgoing | both
get_graph(entry_id, depth)
```
