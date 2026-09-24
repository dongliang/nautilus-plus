/*
 * Copyright (C) 2026 The GNOME project contributors
 *
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * Grouped view support: the fork hook that partitions a file view into
 * groups driven by the "group" extension attribute written by extensions
 * (e.g. nautilus-meta.py writes "已归档" for archived projects).
 *
 * The hook only reads the extension attribute; it does not care who writes
 * it. The group contract — attribute name "group", NULL and "" both meaning
 * "ungrouped" — lives here so both views share it.
 */

#include "nautilus-grouped-view.h"

#include "nautilus-view-item.h"

static GQuark group_quark;

static GQuark
get_group_quark (void)
{
    if (G_UNLIKELY (group_quark == 0))
    {
        group_quark = g_quark_from_static_string ("group");
    }

    return group_quark;
}

/* Compare two group keys. NULL and "" are both "ungrouped": equal to each
 * other, and smaller than any non-empty key. The archived group is always
 * last; other non-empty keys retain their original strcmp ordering. */
static gint
compare_group_keys (const char *key_a,
                    const char *key_b)
{
    gboolean archived_a = g_strcmp0 (key_a, ARCHIVED_GROUP_KEY) == 0;
    gboolean archived_b = g_strcmp0 (key_b, ARCHIVED_GROUP_KEY) == 0;

    if (archived_a != archived_b)
    {
        return archived_a ? GTK_ORDERING_LARGER : GTK_ORDERING_SMALLER;
    }
    if (archived_a)
    {
        return GTK_ORDERING_EQUAL;
    }

    if (key_a == NULL || key_a[0] == '\0')
    {
        if (key_b == NULL || key_b[0] == '\0')
        {
            return GTK_ORDERING_EQUAL;
        }

        return GTK_ORDERING_SMALLER;
    }
    if (key_b == NULL || key_b[0] == '\0')
    {
        return GTK_ORDERING_LARGER;
    }

    return strcmp (key_a, key_b);
}

char *
nautilus_grouped_view_get_group_string (NautilusFile *file)
{
    g_return_val_if_fail (NAUTILUS_IS_FILE (file), NULL);

    /* Not nautilus_file_get_string_attribute_q: the built-in "group"
     * attribute resolves to the POSIX group name and would shadow the
     * extension attribute (see nautilus-file.c). */
    return nautilus_file_get_extension_attribute (file, get_group_quark ());
}

static gint
group_sorter_compare (gconstpointer a,
                      gconstpointer b,
                      gpointer      user_data)
{
    g_autofree char *group_a = NULL;
    g_autofree char *group_b = NULL;

    group_a = nautilus_grouped_view_get_group_string (nautilus_view_item_get_file ((NautilusViewItem *) a));
    group_b = nautilus_grouped_view_get_group_string (nautilus_view_item_get_file ((NautilusViewItem *) b));

    return compare_group_keys (group_a, group_b);
}

static gint
section_sorter_compare (gconstpointer a,
                        gconstpointer b,
                        gpointer      user_data)
{
    g_autoptr (NautilusViewItem) item_a = NAUTILUS_VIEW_ITEM (gtk_tree_list_row_get_item (GTK_TREE_LIST_ROW ((gpointer) a)));
    g_autoptr (NautilusViewItem) item_b = NAUTILUS_VIEW_ITEM (gtk_tree_list_row_get_item (GTK_TREE_LIST_ROW ((gpointer) b)));
    g_autofree char *group_a = NULL;
    g_autofree char *group_b = NULL;

    group_a = nautilus_grouped_view_get_group_string (nautilus_view_item_get_file (item_a));
    group_b = nautilus_grouped_view_get_group_string (nautilus_view_item_get_file (item_b));

    /* This sorter must provide full ordering, not just equality. GtkSortListModel
     * sorts by [section_sorter, sorter]: the section sorter is the primary
     * ordering key, so it decides both the order of sections and where items
     * land. An equality-only sorter would leave section order unspecified. */
    return compare_group_keys (group_a, group_b);
}

GtkSorter *
nautilus_grouped_view_create_group_sorter (void)
{
    return GTK_SORTER (gtk_custom_sorter_new (group_sorter_compare, NULL, NULL));
}

GtkSorter *
nautilus_grouped_view_create_sorter (GtkSorter *fallback)
{
    g_autoptr (GtkMultiSorter) multi_sorter = gtk_multi_sorter_new ();

    gtk_multi_sorter_append (multi_sorter, nautilus_grouped_view_create_group_sorter ());
    gtk_multi_sorter_append (multi_sorter, g_object_ref (fallback));

    return GTK_SORTER (g_steal_pointer (&multi_sorter));
}

GtkSorter *
nautilus_grouped_view_create_section_sorter (void)
{
    return GTK_SORTER (gtk_custom_sorter_new (section_sorter_compare, NULL, NULL));
}
