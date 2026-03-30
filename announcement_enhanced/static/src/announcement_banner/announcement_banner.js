/** @odoo-module */
import { Component, useState, markup } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { NavBar } from "@web/webclient/navbar/navbar";
import { patch } from "@web/core/utils/patch";
import { session } from "@web/session";
import { _lt } from "@web/core/l10n/translation";
import { AnnouncementDialog } from "@announcement/js/announcement_dialog/announcement_dialog.esm";

export class AnnouncementBanner extends Component {
    static template = "announcement_enhanced.AnnouncementBanner";
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.dialogService = useService("dialog");
        const announcementService = useService("announcementService");
        this.announcements = useState(announcementService.announcements);
    }

    get currentAnnouncement() {
        return this.announcements.data && this.announcements.data.length > 0
            ? this.announcements.data[0]
            : null;
    }

    get shouldShow() {
        return Boolean(this.currentAnnouncement);
    }

    openAnnouncement() {
        const ann = this.currentAnnouncement;
        if (!ann) return;
        this.dialogService.add(AnnouncementDialog, {
            title: ann.name,
            body: markup(ann.content || ""),
            confirm: async () => {
                await this.orm.call(
                    "res.users",
                    "mark_announcement_as_read",
                    [ann.id],
                    { context: session.user_context }
                );
                this.announcements.data = this.announcements.data.filter(
                    (el) => el.id !== ann.id
                );
                this.announcements.count = Math.max(0, this.announcements.count - 1);
            },
            confirmLabel: _lt("Mark as read"),
        });
    }

}

patch(NavBar, {
    components: {
        ...NavBar.components,
        AnnouncementBanner,
    },
});
