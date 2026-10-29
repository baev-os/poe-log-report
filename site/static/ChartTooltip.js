"use strict";

class ChartTooltip {
    constructor() {
        this.tooltip = document.createElement("div");
        this.tooltip.className = "chart-tooltip";
        this.tooltip.id = "chart-measurement-tooltip";
        this.tooltip.setAttribute("role", "tooltip");
        this.tooltip.hidden = true;
        document.body.append(this.tooltip);
        this.active = null;
        this.prepare(document);
        document.querySelectorAll("[data-chart-line]:not(.chart-hit)").forEach(line => {
            const hit = line.cloneNode(false);
            hit.removeAttribute("id");
            hit.setAttribute("class", "chart-hit");
            hit.setAttribute("aria-hidden", "true");
            line.after(hit);
        });
        document.addEventListener("pointerover", event => this.prepare(event.target.closest("svg")));
        document.addEventListener("pointermove", event => this.hover(event));
        document.addEventListener("focusin", event => {
            this.prepare(event.target.closest("svg"));
            const target = event.target.closest("[data-chart-tip]");
            if (target && !target.closest("[data-point-tooltip]")) this.show(target);
        });
        document.addEventListener("focusout", event => {
            if (event.target === this.active && !event.target.matches(":hover")) this.hide();
        });
        document.addEventListener("keydown", event => {
            if (event.key === "Escape") this.hide();
            if (!event.target.matches("[data-intensity-hit]") || !["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
            const points = [...event.target.closest("[data-intensity-row]").children];
            let index = points.indexOf(event.target) + (event.key === "ArrowLeft" ? -1 : 1);
            if (event.key === "Home") index = 0;
            if (event.key === "End") index = points.length - 1;
            points[Math.max(0, Math.min(points.length - 1, index))].focus();
            event.preventDefault();
        });
        for (const event of ["input", "change", "click"]) document.addEventListener(event, () => this.hide());
        document.addEventListener("keydown", event => {if (event.key === "Enter" || event.key === " ") this.hide();});
        document.addEventListener("scroll", () => this.hide(), true);
        document.addEventListener("pointerleave", () => this.hide());
        window.addEventListener("resize", () => this.hide());
    }

    prepare(root) {
        if (!root) return;
        root.querySelectorAll("svg title, title").forEach(title => {
            const parent = title.parentElement;
            if (!parent.closest("svg") || parent.tagName.toLowerCase() === "svg" || title.id) return;
            const target = parent.closest("a") || parent;
            target.dataset.chartTip = title.textContent.trim();
            target.setAttribute("aria-label", title.textContent.trim());
            if (!target.closest("a") && !target.hasAttribute("tabindex")) target.setAttribute("tabindex", "0");
            title.remove();
        });
    }

    hover(event) {
        let target = event.target.closest("[data-chart-tip]");
        if (event.target.closest("[data-chart-line]")) {
            const points = [...event.target.closest("svg").querySelectorAll("circle")];
            let distance = Infinity;
            for (const point of points) {
                const box = point.getBoundingClientRect();
                const current = Math.hypot(event.clientX - box.x - box.width / 2, event.clientY - box.y - box.height / 2);
                if (current < distance && point.closest("[data-chart-tip]")) {
                    distance = current;
                    target = point.closest("[data-chart-tip]");
                }
            }
        }
        if (target && !event.target.closest("[data-point-tooltip]")) this.show(target, event);
        else if (!this.active?.matches(":focus-visible")) this.hide();
    }

    show(target, event = null) {
        if (this.active && this.active !== target) this.active.removeAttribute("aria-describedby");
        this.active = target;
        target.setAttribute("aria-describedby", this.tooltip.id);
        this.tooltip.textContent = target.dataset.chartTip;
        this.tooltip.hidden = false;
        const anchor = target.getBoundingClientRect();
        const box = this.tooltip.getBoundingClientRect();
        const x = event ? event.clientX : anchor.x + anchor.width / 2;
        const y = event ? event.clientY : anchor.y;
        this.tooltip.style.left = `${Math.max(8, Math.min(innerWidth - box.width - 8, x - box.width / 2))}px`;
        this.tooltip.style.top = `${Math.max(8, Math.min(innerHeight - box.height - 8, y >= box.height + 16 ? y - box.height - 12 : y + 20))}px`;
    }

    hide() {
        this.tooltip.hidden = true;
    }
}

document.addEventListener("DOMContentLoaded", () => new ChartTooltip());
