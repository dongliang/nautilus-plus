/*
 * Copyright (C) 2026 The GNOME project contributors
 *
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

#include "nautilus-hidden-group-card.h"

#include <glib/gi18n.h>

enum
{
    PROP_0,
    PROP_GROUP_NAME,
    PROP_COUNT,
    PROP_DETAILS,
    N_PROPS
};

enum
{
    ACTIVATE,
    LAST_SIGNAL
};

static GParamSpec *properties[N_PROPS] = { NULL, };
static guint signals[LAST_SIGNAL];

struct _NautilusHiddenGroupCard
{
    GObject parent_instance;

    char *group_name;
    guint count;
    char *details;
};

G_DEFINE_TYPE (NautilusHiddenGroupCard, nautilus_hidden_group_card, G_TYPE_OBJECT)

static void
nautilus_hidden_group_card_finalize (GObject *object)
{
    NautilusHiddenGroupCard *self = NAUTILUS_HIDDEN_GROUP_CARD (object);

    g_clear_pointer (&self->group_name, g_free);
    g_clear_pointer (&self->details, g_free);

    G_OBJECT_CLASS (nautilus_hidden_group_card_parent_class)->finalize (object);
}

static void
nautilus_hidden_group_card_get_property (GObject    *object,
                                         guint       prop_id,
                                         GValue     *value,
                                         GParamSpec *pspec)
{
    NautilusHiddenGroupCard *self = NAUTILUS_HIDDEN_GROUP_CARD (object);

    switch (prop_id)
    {
        case PROP_GROUP_NAME:
            g_value_set_string (value, self->group_name);
            break;
        case PROP_COUNT:
            g_value_set_uint (value, self->count);
            break;
        case PROP_DETAILS:
            g_value_set_string (value, self->details);
            break;
        default:
            G_OBJECT_WARN_INVALID_PROPERTY_ID (object, prop_id, pspec);
    }
}

static void
nautilus_hidden_group_card_set_property (GObject      *object,
                                         guint         prop_id,
                                         const GValue *value,
                                         GParamSpec   *pspec)
{
    NautilusHiddenGroupCard *self = NAUTILUS_HIDDEN_GROUP_CARD (object);

    switch (prop_id)
    {
        case PROP_GROUP_NAME:
            g_set_str (&self->group_name, g_value_get_string (value));
            break;
        case PROP_COUNT:
            self->count = g_value_get_uint (value);
            break;
        case PROP_DETAILS:
            g_set_str (&self->details, g_value_get_string (value));
            break;
        default:
            G_OBJECT_WARN_INVALID_PROPERTY_ID (object, prop_id, pspec);
    }
}

static void
nautilus_hidden_group_card_class_init (NautilusHiddenGroupCardClass *klass)
{
    GObjectClass *object_class = G_OBJECT_CLASS (klass);

    object_class->finalize = nautilus_hidden_group_card_finalize;
    object_class->get_property = nautilus_hidden_group_card_get_property;
    object_class->set_property = nautilus_hidden_group_card_set_property;

    properties[PROP_GROUP_NAME] =
        g_param_spec_string ("group-name", NULL, NULL, NULL,
                             G_PARAM_READWRITE | G_PARAM_CONSTRUCT_ONLY |
                             G_PARAM_STATIC_STRINGS);
    properties[PROP_COUNT] =
        g_param_spec_uint ("count", NULL, NULL, 0, G_MAXUINT, 0,
                           G_PARAM_READWRITE | G_PARAM_STATIC_STRINGS);
    properties[PROP_DETAILS] =
        g_param_spec_string ("details", NULL, NULL, NULL,
                             G_PARAM_READWRITE | G_PARAM_STATIC_STRINGS);
    g_object_class_install_properties (object_class, N_PROPS, properties);

    signals[ACTIVATE] =
        g_signal_new ("activate",
                      G_TYPE_FROM_CLASS (klass),
                      G_SIGNAL_RUN_LAST,
                      0, NULL, NULL,
                      g_cclosure_marshal_VOID__VOID,
                      G_TYPE_NONE, 0);
}

static void
nautilus_hidden_group_card_init (NautilusHiddenGroupCard *self)
{
}

NautilusHiddenGroupCard *
nautilus_hidden_group_card_new (const char *group_name)
{
    return g_object_new (NAUTILUS_TYPE_HIDDEN_GROUP_CARD,
                         "group-name", group_name,
                         NULL);
}

void
nautilus_hidden_group_card_set_summary (NautilusHiddenGroupCard *self,
                                        guint                    count,
                                        const char              *details)
{
    g_return_if_fail (NAUTILUS_IS_HIDDEN_GROUP_CARD (self));

    g_object_freeze_notify (G_OBJECT (self));
    if (self->count != count)
    {
        self->count = count;
        g_object_notify_by_pspec (G_OBJECT (self), properties[PROP_COUNT]);
    }
    if (g_set_str (&self->details, details))
    {
        g_object_notify_by_pspec (G_OBJECT (self), properties[PROP_DETAILS]);
    }
    g_object_thaw_notify (G_OBJECT (self));
}

guint
nautilus_hidden_group_card_get_count (NautilusHiddenGroupCard *self)
{
    g_return_val_if_fail (NAUTILUS_IS_HIDDEN_GROUP_CARD (self), 0);

    return self->count;
}

const char *
nautilus_hidden_group_card_get_group_name (NautilusHiddenGroupCard *self)
{
    g_return_val_if_fail (NAUTILUS_IS_HIDDEN_GROUP_CARD (self), NULL);

    return self->group_name;
}

const char *
nautilus_hidden_group_card_get_details (NautilusHiddenGroupCard *self)
{
    g_return_val_if_fail (NAUTILUS_IS_HIDDEN_GROUP_CARD (self), NULL);

    return self->details;
}

void
nautilus_hidden_group_card_activate (NautilusHiddenGroupCard *self)
{
    g_return_if_fail (NAUTILUS_IS_HIDDEN_GROUP_CARD (self));

    g_signal_emit (self, signals[ACTIVATE], 0);
}

static void
update_widget (NautilusHiddenGroupCard *self,
               GParamSpec              *pspec,
               GtkWidget               *button)
{
    GtkLabel *title = g_object_get_data (G_OBJECT (button), "card-title");
    GtkLabel *count = g_object_get_data (G_OBJECT (button), "card-count");
    GtkLabel *details = g_object_get_data (G_OBJECT (button), "card-details");
    g_autofree char *count_text = NULL;

    gtk_label_set_label (title, self->group_name);
    count_text = g_strdup_printf (_("%u hidden"), self->count);
    gtk_label_set_label (count, count_text);
    gtk_label_set_label (details, self->details != NULL ? self->details : "");
    gtk_widget_set_visible (GTK_WIDGET (details),
                            self->details != NULL && self->details[0] != '\0');
}

static void
on_button_clicked (GtkButton *button,
                   gpointer   user_data)
{
    nautilus_hidden_group_card_activate (NAUTILUS_HIDDEN_GROUP_CARD (user_data));
}

GtkWidget *
nautilus_hidden_group_card_create_widget (NautilusHiddenGroupCard *self,
                                          gboolean                 grid_mode,
                                          guint                    icon_size)
{
    GtkWidget *button;
    GtkWidget *box;
    GtkWidget *icon;
    GtkWidget *title;
    GtkWidget *count;
    GtkWidget *details;

    g_return_val_if_fail (NAUTILUS_IS_HIDDEN_GROUP_CARD (self), NULL);

    button = gtk_button_new ();
    box = gtk_box_new (grid_mode ? GTK_ORIENTATION_VERTICAL :
                                   GTK_ORIENTATION_HORIZONTAL,
                       grid_mode ? 4 : 12);
    icon = gtk_image_new_from_icon_name ("view-conceal-symbolic");
    title = gtk_label_new (NULL);
    count = gtk_label_new (NULL);
    details = gtk_label_new (NULL);

    gtk_widget_add_css_class (button, "hidden-group-card");
    gtk_widget_add_css_class (button, grid_mode ? "grid" : "list");
    gtk_widget_add_css_class (title, "heading");
    gtk_widget_add_css_class (count, "dim-label");
    gtk_widget_add_css_class (details, "caption");
    gtk_widget_add_css_class (details, "dim-label");

    gtk_widget_set_halign (title, grid_mode ? GTK_ALIGN_CENTER : GTK_ALIGN_START);
    gtk_widget_set_halign (count, grid_mode ? GTK_ALIGN_CENTER : GTK_ALIGN_START);
    gtk_widget_set_halign (details, grid_mode ? GTK_ALIGN_CENTER : GTK_ALIGN_START);
    gtk_label_set_ellipsize (GTK_LABEL (details), PANGO_ELLIPSIZE_END);
    gtk_label_set_lines (GTK_LABEL (details), grid_mode ? 2 : 1);
    gtk_label_set_wrap (GTK_LABEL (details), grid_mode);
    gtk_label_set_xalign (GTK_LABEL (details), grid_mode ? 0.5 : 0.0);

    if (grid_mode)
    {
        gtk_widget_set_size_request (button, icon_size + 36, icon_size + 48);
        gtk_image_set_pixel_size (GTK_IMAGE (icon), MIN (icon_size / 2, 48));
        gtk_box_append (GTK_BOX (box), icon);
        gtk_box_append (GTK_BOX (box), title);
        gtk_box_append (GTK_BOX (box), count);
        gtk_box_append (GTK_BOX (box), details);
    }
    else
    {
        GtkWidget *text_box = gtk_box_new (GTK_ORIENTATION_VERTICAL, 2);

        gtk_image_set_pixel_size (GTK_IMAGE (icon), 32);
        gtk_box_append (GTK_BOX (text_box), title);
        gtk_box_append (GTK_BOX (text_box), count);
        gtk_box_append (GTK_BOX (text_box), details);
        gtk_box_append (GTK_BOX (box), icon);
        gtk_box_append (GTK_BOX (box), text_box);
    }

    gtk_button_set_child (GTK_BUTTON (button), box);
    gtk_widget_set_tooltip_text (button, _("Show archived folders temporarily"));
    gtk_accessible_update_property (GTK_ACCESSIBLE (button),
                                    GTK_ACCESSIBLE_PROPERTY_ROLE_DESCRIPTION,
                                    _("Hidden group summary"),
                                    -1);

    g_object_set_data (G_OBJECT (button), "card-title", title);
    g_object_set_data (G_OBJECT (button), "card-count", count);
    g_object_set_data (G_OBJECT (button), "card-details", details);
    g_signal_connect_object (self, "notify",
                             G_CALLBACK (update_widget),
                             button, 0);
    g_signal_connect_object (button, "clicked",
                             G_CALLBACK (on_button_clicked),
                             self, 0);
    update_widget (self, NULL, button);

    return button;
}
