/*
 * Copyright (C) 2026 The GNOME project contributors
 *
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

#pragma once

#include "nautilus-file.h"

#include <gtk/gtk.h>

G_BEGIN_DECLS

/* Group key of a file: the "group" extension attribute, or NULL if the file
 * is not in any group. Ungrouped items sort first and get no group header. */
char *nautilus_grouped_view_get_group_string (NautilusFile *file);

/* Custom sorter over NautilusViewItem: groups first, then strcmp on the
 * group key. Append this as the primary sorter of a multi-sorter whose
 * remaining components order items within a group. */
GtkSorter *nautilus_grouped_view_create_group_sorter (void);

/* Convenience: GtkMultiSorter[group_sorter, fallback]. Takes a reference
 * on fallback. */
GtkSorter *nautilus_grouped_view_create_sorter (GtkSorter *fallback);

/* Custom sorter over GtkTreeListRow, for
 * nautilus_view_model_set_section_sorter. Must provide full ordering, not
 * just equality, because GtkSortListModel sorts by [section_sorter, sorter]
 * — the section sorter is the primary ordering key (see grouped-view.c). */
GtkSorter *nautilus_grouped_view_create_section_sorter (void);

G_END_DECLS
