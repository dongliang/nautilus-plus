/*
 * Copyright (C) 2026 The GNOME project contributors
 *
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

#pragma once

#include "nautilus-view-item.h"

#include <gtk/gtk.h>

G_BEGIN_DECLS

#define NAUTILUS_TYPE_ARCHIVED_FILTER (nautilus_archived_filter_get_type())

G_DECLARE_FINAL_TYPE (NautilusArchivedFilter, nautilus_archived_filter,
                      NAUTILUS, ARCHIVED_FILTER, GtkFilter)

/* Filter over NautilusViewItem that rejects folders carrying the archived
 * group key ("已归档" via the "group" extension attribute). Enabled state
 * is controlled with the "enabled" property; disabled = match everything.
 * Part of the hide-archived feature: see plus/docs/design/hide-archived.md */
NautilusArchivedFilter *nautilus_archived_filter_new (void);

void nautilus_archived_filter_set_enabled (NautilusArchivedFilter *self,
                                           gboolean                enabled);

gboolean nautilus_archived_filter_get_enabled (NautilusArchivedFilter *self);

G_END_DECLS
