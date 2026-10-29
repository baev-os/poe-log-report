"use strict";

class BasicReportBrowserTests {
    static tooltip(node, assert, expected) {
        node.scrollIntoView({block: "center"});
        const box = node.getBoundingClientRect();
        const coordinates = {bubbles: true, clientX: box.x + box.width / 2, clientY: box.y + box.height / 2};
        node.dispatchEvent(new PointerEvent("pointerover", coordinates));
        node.dispatchEvent(new PointerEvent("pointermove", coordinates));
        const tooltip = document.getElementById("chart-measurement-tooltip");
        assert(tooltip && !tooltip.hidden && expected.test(tooltip.textContent), "Tooltip contains both measured coordinates");
        const bounds = tooltip.getBoundingClientRect();
        assert(bounds.x >= 0 && bounds.right <= innerWidth && bounds.y >= 0 && bounds.bottom <= innerHeight, "Tooltip stays within the viewport");
        document.dispatchEvent(new KeyboardEvent("keydown", {key: "Escape"}));
        assert(tooltip.hidden, "Escape closes the tooltip");

        if (node.hasAttribute("tabindex")) {
            node.focus();
            assert(!tooltip.hidden && expected.test(tooltip.textContent), "Tooltip is keyboard accessible");
            node.blur();
        }
    }

    static run() {
        const checks = [];
        const assert = (condition, message) => {checks.push(message); if (!condition) throw new Error(message);};

        try {
            const params = new URLSearchParams(location.search);
            const kind = params.get("kind");
            assert(document.documentElement.dataset.bsTheme === params.get("theme"), "Link applies the shared theme");
            assert(document.querySelector('link[href$="/style.css"],link[href="style.css"]') && document.querySelector('link[href$="bootstrap.min.css"]'), "Extended report's shared styles are loaded");
            const toggle = document.querySelector("[data-theme-toggle]");
            toggle.click();
            assert(document.documentElement.dataset.bsTheme !== params.get("theme"), "Shared switch changes the theme");
            toggle.click();
            assert(document.documentElement.dataset.bsTheme === params.get("theme"), "Switching again restores the theme");
            assert([...document.querySelectorAll('.basic-menu nav a')].every(link => new URL(link.href).searchParams.get('theme') === params.get('theme')), "Navigation retains the theme");
            assert(document.querySelector('a.report-pdf[download="report.pdf"]')?.getAttribute('href').endsWith('/report.pdf'), "Report has a PDF download button");
            assert(/Скачать PDF|Download PDF/.test(document.querySelector('a.report-pdf').textContent), "PDF button is labeled as a download");
            assert(document.querySelectorAll(".basic-menu nav a").length === 5, "Five menu pages");
            assert(document.documentElement.scrollWidth <= innerWidth + 1, "Page width fits the viewport");

            if (innerWidth > 850) assert(document.querySelector("main").getBoundingClientRect().top <= 1, "Short pages start at the top");

            if (innerWidth <= 800) assert(document.querySelector("main").getBoundingClientRect().top - document.querySelector(".basic-menu").getBoundingClientRect().bottom <= 40, "Narrow screens have no extra gap below the menu");

            assert(!document.querySelector('a[href*="technical/"],a[href*="#line-"]'), "No line-number links");
            assert(!document.querySelector("script:not([src])"), "No inline code");
            assert(document.querySelector(".period strong").textContent.trim().length > 0, "Period is always visible");

            if (kind === "graphs") {
                const image = document.querySelector(".activity-overview");
                assert(image.naturalWidth === 4800, "High-resolution image");
                assert(image.compareDocumentPosition(document.querySelector("[data-activity-chart]")) & Node.DOCUMENT_POSITION_FOLLOWING, "Image precedes the interactive chart");
                assert(!document.querySelector('a.button[href$=".png"]') && image.closest('a[href$=".png"]'), "Image opens without a separate button");
                BasicReportBrowserTests.tooltip(document.querySelector(".cumulative-chart circle"), assert, /2026-\d\d-\d\d.*\d+:\d{2}:\d{2}/);
                BasicReportBrowserTests.tooltip(document.querySelector(".cumulative-chart .chart-hit"), assert, /2026-\d\d-\d\d.*\d+:\d{2}:\d{2}/);
                const panel = document.querySelector("[data-daily-chart]");
                const overview = panel.querySelector(".daily-overview");
                const overviewCount = overview.querySelectorAll("rect").length;
                assert(overviewCount === JSON.parse(panel.dataset.days).length, "Overview chart includes every day in the period");
                BasicReportBrowserTests.tooltip(overview.querySelector("rect"), assert, /2026-\d\d-\d\d.*\d+:\d{2}:\d{2}/);
                BasicReportBrowserTests.tooltip(document.querySelector(".basic-time-balance rect"), assert, /\d+:\d{2}:\d{2}.*%/);
                const summary = document.querySelector(".activity-totals");
                assert(summary.querySelectorAll("thead th").length === 3 && summary.querySelectorAll(".activity-group-total").length === 17, "All area groups without the unfinished column");
                assert([...summary.querySelectorAll('a[href^="#"]')].every(link => document.getElementById(link.hash.slice(1))), "Summary links reach charts without technical pages");
                const group = panel.querySelector("[data-daily-group]");
                assert(group.value === "weeks", "Long periods are grouped by week");
                const bar = panel.querySelector("[data-daily-svg] .bar");
                bar.dispatchEvent(new KeyboardEvent("keydown", {key: "Enter", bubbles: true}));
                assert(group.value === "days", "Weekly bars open days through the keyboard");
                assert(panel.querySelectorAll("[data-daily-svg] .bar").length <= 7, "Zoom contains one week");
                assert(overview.querySelectorAll("rect").length === overviewCount, "Week selection preserves the full chart");
                const zoom = panel.querySelector("[data-daily-zoom]");
                const width = Number(panel.querySelector("[data-daily-svg]").getAttribute("viewBox").split(" ")[2]);
                zoom.value = "4"; zoom.dispatchEvent(new Event("input"));
                assert(Number(panel.querySelector("[data-daily-svg]").getAttribute("viewBox").split(" ")[2]) >= width, "Zoom expands the chart");
                const from = panel.querySelector("[data-daily-from]"), to = panel.querySelector("[data-daily-to]");
                from.value = "2030-01-02"; to.value = "2030-01-01"; from.dispatchEvent(new Event("input"));
                assert(from.getAttribute("aria-invalid") === "true" && !panel.querySelector("[data-daily-svg] .bar"), "Invalid ranges do not display false values");
                panel.querySelector("[data-daily-reset]").click();
                assert(group.value === "weeks" && panel.querySelectorAll("[data-daily-svg] .bar").length > 5, "Reset restores the entire period");
                BasicReportBrowserTests.tooltip(panel.querySelector("[data-daily-svg] .bar"), assert, /2026-\d\d-\d\d.*\d+:\d{2}:\d{2}/);
                assert([...panel.querySelectorAll("svg text")].some(node => /^\d+:\d{2}$/.test(node.textContent)), "Bars show hours and minutes");
                const activity = document.querySelector("[data-activity-period]");
                assert(activity.options.length > 2, "Special-area months are selectable");
                activity.selectedIndex = 1; activity.dispatchEvent(new Event("change"));
                assert([...document.querySelectorAll("[data-activity-visit]")].some(node => node.style.display === "none"), "Month selection hides other dates' visits");
                activity.selectedIndex = 0; activity.dispatchEvent(new Event("change"));
                assert([...document.querySelectorAll("[data-activity-visit]")].every(node => node.style.display !== "none"), "Full period restores visits");
            }

            if (kind === "characters") {
                const summary = document.querySelector(".character-list");
                assert(summary.querySelectorAll("thead th").length === 6, "Character summary contains class, levels, level-ups, and deaths");
                assert([...summary.querySelectorAll("tbody a")].every(link => document.getElementById(link.hash.slice(1))), "Summary links to character charts");
                assert(document.querySelectorAll(".character-chart circle").length >= 3, "Level charts omit line chronology");
                BasicReportBrowserTests.tooltip(document.querySelector(".character-chart circle"), assert, /2026.*\d{2}:\d{2}:\d{2}.*(?:level|уровень)/i);
                BasicReportBrowserTests.tooltip(document.querySelector(".character-chart .chart-hit"), assert, /2026.*\d{2}:\d{2}:\d{2}.*(?:level|уровень)/i);
            }

            if (kind === "maps") {
                assert(document.querySelector(".share-bar").textContent.includes("%"), "Percentages in the compact map table");
                const slices = [...document.querySelectorAll(".map-pie path")];
                assert(slices.length === document.querySelectorAll("tbody tr").length, "Pie sectors correspond to map rows");
                BasicReportBrowserTests.tooltip(slices[0], assert, /Synthetic.*\d.*%/);
            }

            if (kind === "calendar") {
                const link = document.querySelector("[data-calendar-day]");
                assert(link.classList.contains("calendar-day") && link.querySelector("strong"), "The entire day card is a link");
                assert(link.getAttribute('href').startsWith('#'), "Day selection does not reload solely for theme changes");
                link.querySelector("strong").click();
                assert(document.getElementById(link.hash.slice(1)).open, "Clicking time within a day card opens details");
                assert(document.querySelectorAll(".calendar-grid").length >= 3, "All months remain present");
            }

            if (kind === "conversations") {
                assert([...document.querySelectorAll("[data-chat-group]")].every(group => !group.open), "Conversation groups start collapsed");
                const sort = document.querySelector("[data-chat-sort]");

                for (const key of ["character", "channel", "utc"]) {
                    sort.value = key; sort.dispatchEvent(new Event("change"));
                    const values = [...document.querySelectorAll("[data-message]")].map(row => row.dataset[key]);
                    assert(values.every((value, index) => !index || values[index - 1].localeCompare(value, document.documentElement.lang) <= 0), `Sorting ${key}`);
                    assert([...document.querySelectorAll("[data-chat-group]")].every(group => new Set([...group.querySelectorAll("[data-message]")].map(row => row.dataset[key === "utc" ? "day" : key])).size === 1), `Grouped expansions ${key}`);
                }

                const search = document.querySelector("[data-chat-search]");
                search.value = "danger & text"; search.dispatchEvent(new Event("input"));
                assert([...document.querySelectorAll("[data-message]")].filter(row => !row.hidden).length === 1, "Conversation search");
                assert([...document.querySelectorAll("[data-chat-group]")].filter(group => !group.hidden).every(group => group.open), "Search expands matching messages");
                assert(document.querySelector(".message-text").textContent.length > 0 && !document.querySelector(".message-text script"), "Messages remain plain text");
                search.value = ""; search.dispatchEvent(new Event("input"));
                assert(document.querySelector(".chat-message .character") && document.querySelector(".channel"), "Character and conversation highlighting");
            }

            document.getElementById("browser-checks").textContent = JSON.stringify({passed: true, checks: checks.length});
        } catch (error) {
            document.getElementById("browser-checks").textContent = JSON.stringify({passed: false, checks: checks.length, error: error.message});
        }
    }
}

window.addEventListener("load", () => BasicReportBrowserTests.run());
