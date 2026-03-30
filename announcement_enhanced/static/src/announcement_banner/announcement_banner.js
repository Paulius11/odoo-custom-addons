/** @odoo-module */
import { Component, useState, markup } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { NavBar } from "@web/webclient/navbar/navbar";
import { patch } from "@web/core/utils/patch";
import { session } from "@web/session";

export class AnnouncementBanner extends Component {
    static template = "announcement_enhanced.AnnouncementBanner";
    static props = {};

    setup() {
        this.orm = useService("orm");
        const announcementService = useService("announcementService");
        // Shared reactive object with the systray — mutations update the badge too
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

    get announcementContent() {
        const ann = this.currentAnnouncement;
        return ann ? markup(ann.content || "") : markup("");
    }

    async dismiss() {
        const ann = this.currentAnnouncement;
        if (!ann) return;
        await this.orm.call(
            "res.users",
            "mark_announcement_as_read",
            [ann.id],
            { context: session.user_context }
        );
        // Remove from shared reactive array — badge also decrements immediately
        this.announcements.data = this.announcements.data.filter(
            (el) => el.id !== ann.id
        );
        this.announcements.count = Math.max(0, this.announcements.count - 1);
    }
}

patch(NavBar, {
    components: {
        ...NavBar.components,
        AnnouncementBanner,
    },
});
