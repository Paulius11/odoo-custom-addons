/** @odoo-module **/

/**
 * Debug Field Copy Extension
 *
 * Adds copy functionality to developer-mode field tooltips by:
 * 1. Observing the DOM for new technical tooltips
 * 2. Keeping the tooltip open long enough for the mouse to reach it
 * 3. Adding copy buttons dynamically
 *
 * IMPORTANT: this module must never remove a popover from the DOM itself.
 * Popovers are owned by Owl (see PopoverController); detaching their root node
 * leaves the controller alive with a null ref, and its global "pointerdown"
 * listener then throws on every subsequent click. Closing is always delegated
 * back to the tooltip service by replaying the "mouseleave" it swallowed.
 */

// Selector identifying the developer-mode tooltip content. Only popovers
// containing it are ever touched by this module.
const TECHNICAL_SELECTOR = ".o-tooltip--technical";
// Grace period given to the user to move the mouse from the field to the tooltip.
const REACH_DELAY = 400;
// Marks a synthetic "mouseleave" so it is forwarded to the tooltip service.
const REPLAY_FLAG = "_debugFieldCopyReplay";

// Trigger element whose "mouseleave" was swallowed, waiting to be replayed.
let deferredTrigger = null;
let reachTimeout = null;
let isMouseInPopover = false;

/**
 * Copy text to clipboard and show feedback
 */
async function copyToClipboard(text, button) {
    try {
        await navigator.clipboard.writeText(text);
        showCopyFeedback(button, true);
    } catch (err) {
        // Fallback for older browsers
        const textArea = document.createElement("textarea");
        textArea.value = text;
        textArea.style.cssText = "position:fixed;left:-9999px;top:0";
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        try {
            document.execCommand("copy");
            showCopyFeedback(button, true);
        } catch (e) {
            console.error("Copy failed:", e);
            showCopyFeedback(button, false);
        }
        document.body.removeChild(textArea);
    }
}

function showCopyFeedback(button, success) {
    const icon = button.querySelector("i");
    if (!icon) return;

    const originalClass = icon.className;
    icon.className = success ? "fa fa-check" : "fa fa-times";
    button.style.color = success ? "#4caf50" : "#f44336";

    setTimeout(() => {
        icon.className = originalClass;
        button.style.color = "";
    }, 1500);
}

/**
 * Create a copy button element
 */
function createCopyButton(textToCopy) {
    const btn = document.createElement("button");
    btn.className = "o-tooltip-copy-btn";
    btn.title = "Copy to clipboard";
    btn.type = "button";
    btn.innerHTML = '<i class="fa fa-clipboard"></i>';
    btn.style.cssText = `
        background: transparent;
        border: none;
        color: rgba(255, 255, 255, 0.6);
        cursor: pointer;
        padding: 2px 6px;
        margin-left: 8px;
        border-radius: 3px;
        font-size: 12px;
        flex-shrink: 0;
        transition: all 0.15s ease;
    `;

    btn.onmouseenter = () => {
        btn.style.background = "rgba(255, 255, 255, 0.15)";
        btn.style.color = "#fff";
    };
    btn.onmouseleave = () => {
        btn.style.background = "transparent";
        btn.style.color = "rgba(255, 255, 255, 0.6)";
    };
    btn.onclick = (e) => {
        e.preventDefault();
        e.stopPropagation();
        copyToClipboard(textToCopy, btn);
    };

    return btn;
}

/**
 * Enhance a tooltip element with copy buttons
 */
function enhanceTooltip(tooltipEl) {
    // Check if already enhanced
    if (tooltipEl.dataset.enhanced) return;
    tooltipEl.dataset.enhanced = "true";

    const technicalList = tooltipEl.querySelector(TECHNICAL_SELECTOR);
    if (!technicalList) return;

    // Add copy buttons to each item
    const items = technicalList.querySelectorAll("li[data-item]");
    items.forEach((item) => {
        const title = item.querySelector(".o-tooltip--technical--title");
        if (!title) return;

        // Get the value text
        let valueText = "";
        const childNodes = Array.from(item.childNodes);
        for (const node of childNodes) {
            if (node === title) continue;
            if (node.nodeType === Node.TEXT_NODE) {
                valueText += node.textContent;
            } else if (
                node.nodeType === Node.ELEMENT_NODE &&
                !node.classList.contains("o-tooltip-copy-btn")
            ) {
                valueText += node.textContent;
            }
        }
        valueText = valueText.trim();

        if (valueText) {
            // Style the item as flex row
            item.style.cssText = "display: flex; align-items: center; gap: 8px;";

            // Wrap the value in a span for better layout
            const valueSpan = document.createElement("span");
            valueSpan.style.cssText =
                "flex: 1; word-break: break-all; user-select: text; cursor: text;";
            valueSpan.textContent = valueText;

            // Remove old text nodes
            childNodes.forEach((node) => {
                if (node !== title && node.nodeType === Node.TEXT_NODE) {
                    node.remove();
                }
            });

            // Add value span and copy button
            item.appendChild(valueSpan);
            item.appendChild(createCopyButton(valueText));
        }
    });

    // Make text selectable
    technicalList.style.userSelect = "text";
    technicalList.style.cursor = "text";
}

/**
 * Returns the currently open technical tooltip popover, if any.
 * Never matches regular popovers (dropdowns, avatar cards, date pickers...).
 */
function getTechnicalPopover() {
    for (const popover of document.querySelectorAll(".o_popover")) {
        if (popover.querySelector(TECHNICAL_SELECTOR)) {
            return popover;
        }
    }
    return null;
}

/**
 * Hands the swallowed "mouseleave" back to the tooltip service so that it
 * closes the popover through Owl instead of us detaching the node.
 */
function replayDeferredLeave() {
    clearTimeout(reachTimeout);
    reachTimeout = null;
    const trigger = deferredTrigger;
    deferredTrigger = null;
    if (!trigger || !trigger.isConnected) {
        return;
    }
    const ev = new MouseEvent("mouseleave", { bubbles: false, cancelable: true });
    ev[REPLAY_FLAG] = true;
    trigger.dispatchEvent(ev);
}

/**
 * Setup popover to stay open when mouse enters it
 */
function setupPopoverPersistence(popover) {
    if (popover.dataset.persistenceSetup) return;
    popover.dataset.persistenceSetup = "true";

    // Make popover interactive
    popover.style.pointerEvents = "auto";

    popover.addEventListener("mouseenter", () => {
        isMouseInPopover = true;
        clearTimeout(reachTimeout);
        reachTimeout = null;
    });

    popover.addEventListener("mouseleave", () => {
        isMouseInPopover = false;
        replayDeferredLeave();
    });
}

/**
 * Observe DOM for new tooltips
 */
function observeTooltips() {
    const observer = new MutationObserver((mutations) => {
        for (const mutation of mutations) {
            for (const node of mutation.addedNodes) {
                if (node.nodeType !== Node.ELEMENT_NODE) continue;

                // Check for popover with tooltip
                let popover = null;
                let tooltip = null;

                if (node.classList?.contains("o_popover")) {
                    popover = node;
                    tooltip = node.querySelector(".o-tooltip");
                } else if (node.classList?.contains("o-tooltip")) {
                    tooltip = node;
                    popover = node.closest(".o_popover");
                } else {
                    popover = node.querySelector?.(".o_popover");
                    tooltip = node.querySelector?.(".o-tooltip");
                }

                if (tooltip && tooltip.querySelector(TECHNICAL_SELECTOR)) {
                    setTimeout(() => {
                        if (!tooltip.isConnected) return;
                        enhanceTooltip(tooltip);
                        if (popover) {
                            setupPopoverPersistence(popover);
                        }
                    }, 10);
                }
            }
            // A popover closing while a replay was pending: drop the pending state.
            for (const node of mutation.removedNodes) {
                if (node.nodeType !== Node.ELEMENT_NODE) continue;
                if (node.classList?.contains("o_popover")) {
                    isMouseInPopover = false;
                    clearTimeout(reachTimeout);
                    reachTimeout = null;
                    deferredTrigger = null;
                }
            }
        }
    });

    observer.observe(document.body, {
        childList: true,
        subtree: true,
    });
}

/**
 * Delay the tooltip service's close so the mouse can reach the tooltip.
 *
 * The listener sits on `document`, which is above the `document.body` node the
 * tooltip service listens on: in the capture phase document is reached first,
 * so we can swallow the event whatever the module load order is. The event is
 * always replayed later - either when the mouse leaves the popover, or after
 * REACH_DELAY if it never got there - so the service still performs the close.
 */
function deferTooltipClose() {
    document.addEventListener(
        "mouseleave",
        (ev) => {
            if (ev[REPLAY_FLAG]) {
                // Our own replay: let it through to the tooltip service.
                return;
            }
            const trigger = ev.target.closest?.("[data-tooltip-template], [data-tooltip]");
            if (!trigger) return;

            const popover = getTechnicalPopover();
            if (!popover) return;

            // Moving straight into the tooltip: keep it open, replay on leave.
            const movingToPopover = ev.relatedTarget?.closest?.(".o_popover") === popover;

            ev.stopImmediatePropagation();
            deferredTrigger = trigger;

            if (movingToPopover) {
                isMouseInPopover = true;
                clearTimeout(reachTimeout);
                reachTimeout = null;
                return;
            }

            clearTimeout(reachTimeout);
            reachTimeout = setTimeout(() => {
                reachTimeout = null;
                if (isMouseInPopover || popover.matches(":hover")) {
                    return;
                }
                replayDeferredLeave();
            }, REACH_DELAY);
        },
        { capture: true }
    );
}

// Initialize
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
        observeTooltips();
    });
} else {
    observeTooltips();
}
// Safe at module load: bound to `document`, which exists before <body> is parsed.
deferTooltipClose();
