"use strict";

class BasicReport {
    static svg(tag, attributes = {}, text = null) {
        const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
        for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
        if (text !== null) node.textContent = text;
        return node;
    }

    static duration(seconds, precise = false) {
        const value = Math.round(seconds);
        return `${Math.floor(value / 3600)}:${String(Math.floor(value % 3600 / 60)).padStart(2, "0")}${precise ? `:${String(value % 60).padStart(2, "0")}` : ""}`;
    }

    static daily(panel) {
        const days = JSON.parse(panel.dataset.days);
        if (!days.length) return;
        const svg = panel.querySelector("[data-daily-svg]");
        const group = panel.querySelector("[data-daily-group]");
        const from = panel.querySelector("[data-daily-from]");
        const to = panel.querySelector("[data-daily-to]");
        const zoom = panel.querySelector("[data-daily-zoom]");
        const error = panel.querySelector("[data-daily-error]");
        const render = () => {
            const invalid = !from.validity.valid || !to.validity.valid || (from.value && to.value && from.value > to.value);
            from.setAttribute("aria-invalid", invalid);
            to.setAttribute("aria-invalid", invalid);
            const selected = invalid ? [] : days.filter(day => (!from.value || day.date >= from.value) && (!to.value || day.date <= to.value));
            let rows = selected;
            if (group.value === "weeks") {
                const weeks = new Map();
                for (const day of selected) {
                    const date = new Date(`${day.date}T12:00:00Z`);
                    date.setUTCDate(date.getUTCDate() - (date.getUTCDay() + 6) % 7);
                    const key = date.toISOString().slice(0, 10);
                    const row = weeks.get(key) || {date: key, end: day.date, seconds: 0, first: day.date};
                    row.end = day.date;
                    row.seconds += day.seconds;
                    weeks.set(key, row);
                }
                rows = Array.from(weeks.values());
            }
            const spacing = 90 * Number(zoom.value);
            const width = Math.max(1000, rows.length * spacing + 100);
            const maximum = rows.reduce((maximum, row) => Math.max(maximum, row.seconds), 3600);
            svg.setAttribute("viewBox", `0 0 ${width} 340`);
            svg.style.width = `${width}px`;
            svg.replaceChildren();
            for (let tick = 0; tick <= 4; tick++) {
                const y = 270 - tick * 52;
                svg.append(BasicReport.svg("line", {x1: 60, x2: width - 12, y1: y, y2: y, class: "grid"}));
                svg.append(BasicReport.svg("text", {x: 5, y: y + 4}, (maximum * tick / 4 / 3600).toLocaleString(document.documentElement.lang, {maximumFractionDigits: 1})));
            }
            svg.append(BasicReport.svg("text", {x: 5, y: 20}, panel.dataset.hours));
            rows.forEach((row, index) => {
                const x = 70 + index * spacing;
                const height = row.seconds / maximum * 208;
                const rect = BasicReport.svg("rect", {x, y: 270 - height, width: spacing * .65, height, class: "bar", tabindex: 0});
                rect.append(BasicReport.svg("title", {}, `${row.first || row.date}${row.end ? ` — ${row.end}` : ""} · ${panel.dataset.hours}: ${BasicReport.duration(row.seconds, true)}`));
                if (group.value === "weeks") {
                    rect.setAttribute("role", "button");
                    const expand = () => {from.value = row.first; to.value = row.end; group.value = "days"; render();};
                    rect.addEventListener("click", expand);
                    rect.addEventListener("keydown", event => {if (event.key === "Enter" || event.key === " ") {event.preventDefault(); expand();}});
                }
                svg.append(rect, BasicReport.svg("text", {x: x + spacing * .325, y: 260 - height, "text-anchor": "middle"}, BasicReport.duration(row.seconds)));
                svg.append(BasicReport.svg("text", {x: x + spacing * .325, y: 296, "text-anchor": "middle"}, row.date));
                if (row.end) svg.append(BasicReport.svg("text", {x: x + spacing * .325, y: 314, "text-anchor": "middle"}, row.end));
            });
            error.textContent = invalid ? `${from.value || "…"} > ${to.value || "…"}` : "";
        };
        panel.querySelector("[data-daily-controls]").hidden = false;
        group.value = days.length > 60 ? "weeks" : "days";
        for (const input of [group, from, to, zoom]) input.addEventListener("input", render);
        panel.querySelector("[data-daily-reset]").addEventListener("click", () => {
            from.value = days[0].date; to.value = days.at(-1).date; zoom.value = 1;
            group.value = days.length > 60 ? "weeks" : "days"; render();
        });
        render();
    }

    static activities(panel) {
        const select = panel.querySelector("[data-activity-period]");
        const svg = panel.querySelector("svg");
        const height = svg.viewBox.baseVal.height;
        panel.querySelector("[data-activity-controls]").hidden = false;
        select.addEventListener("change", () => {
            const option = select.selectedOptions[0];
            const start = Number(option.dataset.start), end = Number(option.dataset.end);
            for (const visit of panel.querySelectorAll("[data-activity-visit]")) {
                const left = Number(visit.dataset.start), right = Number(visit.dataset.end);
                const point = left === right;
                const visible = point ? left >= start && (left < end || (option.value === "all" && left === end)) : left < end && right > start;
                visit.hidden = !visible;
                visit.style.display = visible ? "" : "none";
                const x = Math.min(1178.5, 220 + 960 * (Math.max(start, left) - start) / (end - start));
                visit.setAttribute("x", x);
                visit.setAttribute("width", Math.min(1180 - x, Math.max(1.5, 960 * (Math.min(end, right) - Math.max(start, left)) / (end - start))));
            }
            const ticks = panel.querySelector("[data-activity-ticks]");
            ticks.replaceChildren();
            JSON.parse(option.dataset.ticks).forEach((tick, index, values) => {
                ticks.append(BasicReport.svg("line", {x1: tick.x, x2: tick.x, y1: 24, y2: height - 55, class: "grid"}));
                ticks.append(BasicReport.svg("text", {x: tick.x, y: height - 20, "text-anchor": index === values.length - 1 ? "end" : "start"}, tick.label));
            });
        });
    }

    static conversations(panel) {
        const rows = Array.from(panel.querySelectorAll("[data-message]"));
        if (!rows.length) return;
        const sort = panel.querySelector("[data-chat-sort]");
        const search = panel.querySelector("[data-chat-search]");
        const list = panel.querySelector("[data-chat-list]");
        const compareDates = (a, b) => (!a.dataset.utc - !b.dataset.utc) || a.dataset.utc.localeCompare(b.dataset.utc);
        const states = new Map();
        let searching = false;
        const render = () => {
            if (!searching) for (const group of list.querySelectorAll("[data-group-key]")) states.set(group.dataset.groupKey, group.open);
            const key = sort.value;
            rows.sort((a, b) => key === "utc" ? compareDates(a, b) : a.dataset[key].localeCompare(b.dataset[key], document.documentElement.lang) || compareDates(a, b));
            const groups = new Map();
            let visible = 0;
            searching = !!search.value.trim();
            for (const row of rows) {
                row.hidden = !row.textContent.toLocaleLowerCase().includes(search.value.trim().toLocaleLowerCase());
                if (!row.hidden) visible++;
                const name = key === "utc" ? row.dataset.day : row.dataset[key];
                if (!groups.has(name)) groups.set(name, []);
                groups.get(name).push(row);
            }
            list.replaceChildren();
            for (const [name, messages] of groups) {
                const group = document.createElement("details");
                group.className = "chat-group";
                group.dataset.chatGroup = "";
                group.dataset.groupKey = `${key}:${name}`;
                group.open = searching || states.get(group.dataset.groupKey) || false;
                const count = messages.filter(row => !row.hidden).length;
                group.hidden = !count;
                const summary = document.createElement("summary");
                summary.textContent = `${name} · ${count}`;
                const content = document.createElement("ol");
                content.className = "chat-list";
                for (const message of messages) content.append(message);
                group.append(summary, content);
                list.append(group);
            }
            panel.querySelector("[data-chat-count]").textContent = `${visible} / ${rows.length}`;
        };
        panel.querySelector("[data-chat-controls]").hidden = false;
        sort.addEventListener("change", render);
        search.addEventListener("input", render);
        render();
    }

    static start() {
        document.querySelectorAll("[data-daily-chart]").forEach(panel => BasicReport.daily(panel));
        document.querySelectorAll("[data-activity-chart]").forEach(panel => BasicReport.activities(panel));
        const showDay = hash => {
            for (const detail of document.querySelectorAll("[data-calendar-detail]")) {
                detail.hidden = `#${detail.id}` !== hash;
                detail.open = !detail.hidden;
            }
        };
        showDay(location.hash);
        window.addEventListener("hashchange", () => showDay(location.hash));
        document.querySelectorAll("[data-calendar-day]").forEach(link => link.addEventListener("click", () => showDay(link.hash)));
        document.querySelectorAll("[data-chat]").forEach(panel => BasicReport.conversations(panel));
    }
}

document.addEventListener("DOMContentLoaded", () => BasicReport.start());
