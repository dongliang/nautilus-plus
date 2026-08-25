/*
 * Copyright (C) 2026 The GNOME project contributors
 *
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

#include "nautilus-archived-filter.h"

#include "nautilus-global-preferences.h"
#include "nautilus-grouped-view.h"

enum
{
    PROP_0,
    PROP_ENABLED,
    N_PROPS
};

static GParamSpec *properties[N_PROPS] = { NULL, };

struct _NautilusArchivedFilter
{
    GtkFilter parent_instance;

    gboolean enabled;
    gboolean setting_enabled;
    gboolean temporarily_disabled;
    gulong settings_handler_id;
};

G_DEFINE_TYPE (NautilusArchivedFilter, nautilus_archived_filter, GTK_TYPE_FILTER)

static void
hide_archived_changed (NautilusArchivedFilter *self)
{
    self->setting_enabled =
        g_settings_get_boolean (nautilus_preferences, "hide-archived");
    nautilus_archived_filter_set_enabled (
        self, self->setting_enabled && !self->temporarily_disabled);
}

static GtkFilterMatch
nautilus_archived_filter_get_strictness (GtkFilter *filter)
{
    NautilusArchivedFilter *self = NAUTILUS_ARCHIVED_FILTER (filter);

    return (self->enabled ? GTK_FILTER_MATCH_SOME : GTK_FILTER_MATCH_ALL);
}

static gboolean
nautilus_archived_filter_match (GtkFilter *filter,
                                gpointer   item)
{
    NautilusArchivedFilter *self = NAUTILUS_ARCHIVED_FILTER (filter);
    NautilusFile *file;

    if (!self->enabled)
    {
        return TRUE;
    }

    g_return_val_if_fail (NAUTILUS_IS_VIEW_ITEM (item), TRUE);

    file = nautilus_view_item_get_file (NAUTILUS_VIEW_ITEM (item));

    /* Only folders can carry the archived group. */
    if (!nautilus_file_is_directory (file))
    {
        return TRUE;
    }

    /* Extension info providers run asynchronously after items enter the
     * model. Until they have all run, a folder's group key is unknown:
     * hide conservatively now, and let the re-evaluation pass
     * (files-view's idle refilter) admit the non-archived ones. This
     * keeps archived folders from flashing in for a frame. */
    if (nautilus_file_is_extension_info_pending (file))
    {
        return FALSE;
    }

    /* Reuse the grouped-view contract: the archived group key marks
     * folders to hide. NULL/other keys pass through untouched. */
    g_autofree char *group = nautilus_grouped_view_get_group_string (file);

    return (group == NULL ||
            strcmp (group, ARCHIVED_GROUP_KEY) != 0);
}

static void
nautilus_archived_filter_set_property (GObject      *object,
                                       guint         prop_id,
                                       const GValue *value,
                                       GParamSpec   *pspec)
{
    NautilusArchivedFilter *self = NAUTILUS_ARCHIVED_FILTER (object);

    switch (prop_id)
    {
        case PROP_ENABLED:
        {
            nautilus_archived_filter_set_enabled (self, g_value_get_boolean (value));
        }
        break;

        default:
        {
            G_OBJECT_WARN_INVALID_PROPERTY_ID (object, prop_id, pspec);
        }
    }
}

static void
nautilus_archived_filter_get_property (GObject    *object,
                                       guint       prop_id,
                                       GValue     *value,
                                       GParamSpec *pspec)
{
    NautilusArchivedFilter *self = NAUTILUS_ARCHIVED_FILTER (object);

    switch (prop_id)
    {
        case PROP_ENABLED:
        {
            g_value_set_boolean (value, self->enabled);
        }
        break;

        default:
        {
            G_OBJECT_WARN_INVALID_PROPERTY_ID (object, prop_id, pspec);
        }
    }
}

static void
nautilus_archived_filter_finalize (GObject *object)
{
    NautilusArchivedFilter *self = NAUTILUS_ARCHIVED_FILTER (object);

    g_clear_signal_handler (&self->settings_handler_id, nautilus_preferences);

    G_OBJECT_CLASS (nautilus_archived_filter_parent_class)->finalize (object);
}

static void
nautilus_archived_filter_class_init (NautilusArchivedFilterClass *klass)
{
    GObjectClass *object_class = G_OBJECT_CLASS (klass);
    GtkFilterClass *filter_class = GTK_FILTER_CLASS (klass);

    object_class->finalize = nautilus_archived_filter_finalize;
    object_class->get_property = nautilus_archived_filter_get_property;
    object_class->set_property = nautilus_archived_filter_set_property;

    filter_class->get_strictness = nautilus_archived_filter_get_strictness;
    filter_class->match = nautilus_archived_filter_match;

    properties[PROP_ENABLED] = g_param_spec_boolean ("enabled", NULL, NULL,
                                                     FALSE,
                                                     G_PARAM_READWRITE | G_PARAM_STATIC_STRINGS);
    g_object_class_install_properties (object_class, N_PROPS, properties);
}

static void
nautilus_archived_filter_init (NautilusArchivedFilter *self)
{
    self->enabled = FALSE;

    /* The enabled state lives in gsettings (fork-only key): the Python
     * extension writes it, every view instance follows. */
    self->settings_handler_id =
        g_signal_connect_object (nautilus_preferences, "changed::hide-archived",
                                 G_CALLBACK (hide_archived_changed),
                                 self, G_CONNECT_SWAPPED);
    hide_archived_changed (self);
}

NautilusArchivedFilter *
nautilus_archived_filter_new (void)
{
    return g_object_new (NAUTILUS_TYPE_ARCHIVED_FILTER, NULL);
}

void
nautilus_archived_filter_set_enabled (NautilusArchivedFilter *self,
                                      gboolean                enabled)
{
    g_return_if_fail (NAUTILUS_IS_ARCHIVED_FILTER (self));

    enabled = !!enabled;

    if (self->enabled == enabled)
    {
        return;
    }

    self->enabled = enabled;

    /* MORE_STRICT when enabling (items will drop out), LESS_STRICT when
     * disabling — GtkFilterListModel re-matches incrementally either way. */
    gtk_filter_changed (GTK_FILTER (self),
                        enabled ? GTK_FILTER_CHANGE_MORE_STRICT :
                        GTK_FILTER_CHANGE_LESS_STRICT);

    g_object_notify_by_pspec (G_OBJECT (self), properties[PROP_ENABLED]);
}

void
nautilus_archived_filter_set_temporarily_disabled (NautilusArchivedFilter *self,
                                                   gboolean                temporarily_disabled)
{
    g_return_if_fail (NAUTILUS_IS_ARCHIVED_FILTER (self));

    temporarily_disabled = !!temporarily_disabled;
    if (self->temporarily_disabled == temporarily_disabled)
    {
        return;
    }

    self->temporarily_disabled = temporarily_disabled;
    nautilus_archived_filter_set_enabled (
        self, self->setting_enabled && !self->temporarily_disabled);
}

gboolean
nautilus_archived_filter_get_enabled (NautilusArchivedFilter *self)
{
    g_return_val_if_fail (NAUTILUS_IS_ARCHIVED_FILTER (self), FALSE);

    return self->enabled;
}
