/*
 * Copyright (C) 2026 The GNOME project contributors
 *
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

#pragma once

#include <gtk/gtk.h>

G_BEGIN_DECLS

#define NAUTILUS_TYPE_HIDDEN_GROUP_CARD (nautilus_hidden_group_card_get_type ())

G_DECLARE_FINAL_TYPE (NautilusHiddenGroupCard, nautilus_hidden_group_card,
                      NAUTILUS, HIDDEN_GROUP_CARD, GObject)

NautilusHiddenGroupCard *nautilus_hidden_group_card_new (const char *group_name);

void nautilus_hidden_group_card_set_summary (NautilusHiddenGroupCard *self,
                                             guint                    count,
                                             const char              *details);

guint nautilus_hidden_group_card_get_count (NautilusHiddenGroupCard *self);
const char *nautilus_hidden_group_card_get_group_name (NautilusHiddenGroupCard *self);
const char *nautilus_hidden_group_card_get_details (NautilusHiddenGroupCard *self);

/* A presentation of the model. Grid mode constrains it to one normal grid
 * cell's footprint; list mode stretches as an entire section header row. */
GtkWidget *nautilus_hidden_group_card_create_widget (NautilusHiddenGroupCard *self,
                                                     gboolean                 grid_mode,
                                                     guint                    icon_size);

/* Emitted by card widgets when activated. */
void nautilus_hidden_group_card_activate (NautilusHiddenGroupCard *self);

G_END_DECLS
