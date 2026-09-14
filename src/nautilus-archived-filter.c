/*
 * Copyright (C) 2026 The GNOME project contributors
 *
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

#include "nautilus-archived-filter.h"

#include "nautilus-grouped-view.h"

/* Fork-only settings live in the fork's own schema file, never in
 * org.gnome.nautilus.preferences: that schema is owned by the distribution's
 * nautilus package, so a system upgrade replaces the file and drops our key.
 * Reading a key that does not exist aborts the process, so the schema is
 * looked up defensively instead. See plus/docs/pitfalls.md. */
#define PLUS_SCHEMA_ID "org.gnome.NautilusPlus.preferences"
#define HIDE_ARCHIVED_KEY "hide-archived"

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
    GSettings *settings; /* NULL when the fork schema is unavailable */
    gulong settings_handler_id;
};

G_DEFINE_TYPE (NautilusArchivedFilter, nautilus_archived_filter, GTK_TYPE_FILTER)

static GSettings *
create_plus_settings (void)
{
    GSettingsSchemaSource *source;
    GSettingsSchema *schema;
    GSettings *settings = NULL;

    source = g_settings_schema_source_get_default ();
    if (source == NULL)
    {
        return NULL;
    }

    schema = g_settings_schema_source_lookup (source, PLUS_SCHEMA_ID, TRUE);
    if (schema == NULL || !g_settings_schema_has_key (schema, HIDE_ARCHIVED_KEY))
    {
        /* Not a fatal condition: without the key the feature stays off, which
         * is the same as "archived folders are shown". Aborting here would
         * take the whole file manager down on a system that merely upgraded
         * its nautilus package. */
        g_warning_once ("Settings schema '%s' with key '%s' is missing; "
                        "hide-archived stays disabled until nautilus-plus is "
                        "installed again.",
                        PLUS_SCHEMA_ID, HIDE_ARCHIVED_KEY);
    }
    else
    {
        settings = g_settings_new_full (schema, NULL, NULL);
    }

    if (schema != NULL)
    {
        g_settings_schema_unref (schema);
    }

    return settings;
}

static void
hide_archived_changed (NautilusArchivedFilter *self)
{
    self->setting_enabled =
        self->settings != NULL &&
        g_settings_get_boolean (self->settings, HIDE_ARCHIVED_KEY);

    /* A global setting change starts a new visibility state. Do not let a
     * previous card click keep this view in its temporary reveal state when
     * the user turns hiding back on. The setter also re-evaluates enabled and
     * emits the normal filter/notify signals when needed. */
    nautilus_archived_filter_set_temporarily_disabled (self, FALSE);
    nautilus_archived_filter_set_enabled (self, self->setting_enabled);
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

    g_clear_signal_handler (&self->settings_handler_id, self->settings);
    g_clear_object (&self->settings);

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
    self->settings = create_plus_settings ();
    if (self->settings != NULL)
    {
        self->settings_handler_id =
            g_signal_connect_object (self->settings,
                                     "changed::" HIDE_ARCHIVED_KEY,
                                     G_CALLBACK (hide_archived_changed),
                                     self, G_CONNECT_SWAPPED);
    }

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
