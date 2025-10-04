from typing import Dict, List, Tuple
from .models import Change


def diff_snapshots(space_name: str, old_items: Dict[str, Dict], new_items: Dict[str, Dict]) -> List[Change]:
    changes: List[Change] = []

    old_ids = set(old_items.keys())
    new_ids = set(new_items.keys())

    added_ids = new_ids - old_ids
    removed_ids = old_ids - new_ids
    common_ids = old_ids & new_ids

    for item_id in sorted(added_ids):
        item = new_items[item_id]
        changes.append(
            Change(
                space_name=space_name,
                change_type="added",
                item_id=item_id,
                title=item.get("title", item_id),
                url=item.get("url"),
                extra={"hash": item.get("hash")},
            )
        )

    for item_id in sorted(removed_ids):
        item = old_items[item_id]
        changes.append(
            Change(
                space_name=space_name,
                change_type="removed",
                item_id=item_id,
                title=item.get("title", item_id),
                url=item.get("url"),
                extra={"hash": item.get("hash")},
            )
        )

    for item_id in sorted(common_ids):
        old_item = old_items[item_id]
        new_item = new_items[item_id]
        if (old_item.get("hash") != new_item.get("hash")) or (
            old_item.get("title") != new_item.get("title")
        ):
            changes.append(
                Change(
                    space_name=space_name,
                    change_type="modified",
                    item_id=item_id,
                    title=new_item.get("title", item_id),
                    url=new_item.get("url"),
                    extra={
                        "old_hash": old_item.get("hash"),
                        "new_hash": new_item.get("hash"),
                    },
                )
            )

    return changes
