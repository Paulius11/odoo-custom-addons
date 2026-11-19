/** @odoo-module **/
import {click, getFixture, nextTick, triggerHotkey} from "@web/../tests/helpers/utils";
import {makeView, setupViewRegistries} from "@web/../tests/views/helpers";

let serverData = null;
let target = null;

const arch = `
    <tree editable="bottom">
        <field name="name"/>
        <field name="qty"/>
        <field name="note"/>
        <field name="kind"/>
        <field name="email" widget="email"/>
    </tree>`;

/** [column name, row index] of the focused cell */
function position() {
    const cell = document.activeElement.closest("td");
    const rows = [...target.querySelectorAll(".o_data_row")];
    return [cell.getAttribute("name"), rows.indexOf(cell.parentElement)];
}

async function press(key) {
    await triggerHotkey(key);
    await nextTick();
    await nextTick();
}

QUnit.module("web_list_arrow_keys", (hooks) => {
    hooks.beforeEach(() => {
        target = getFixture();
        serverData = {
            models: {
                foo: {
                    fields: {
                        name: {string: "Name", type: "char"},
                        qty: {string: "Qty", type: "integer"},
                        note: {string: "Note", type: "text"},
                        kind: {
                            string: "Kind",
                            type: "selection",
                            selection: [
                                ["a", "A"],
                                ["b", "B"],
                            ],
                        },
                        email: {string: "Email", type: "char"},
                    },
                    records: [
                        {id: 1, name: "aa", qty: 10, note: "xx", kind: "a", email: "e1@x.lt"},
                        {id: 2, name: "bb", qty: 20, note: "yy", kind: "a", email: "e2@x.lt"},
                        {id: 3, name: "cc", qty: 30, note: "zz", kind: "a", email: "e3@x.lt"},
                    ],
                },
            },
        };
        setupViewRegistries();
    });

    QUnit.test("up, down and Enter keep the column", async (assert) => {
        await makeView({type: "list", resModel: "foo", serverData, arch});
        await click(target.querySelector(".o_data_row td[name=qty]"));
        assert.deepEqual(position(), ["qty", 0]);
        await press("ArrowDown");
        assert.deepEqual(position(), ["qty", 1]);
        await press("Enter");
        assert.deepEqual(position(), ["qty", 2]);
        await press("ArrowUp");
        assert.deepEqual(position(), ["qty", 1]);
    });

    QUnit.test("left and right leave a cell only at the text edges", async (assert) => {
        await makeView({type: "list", resModel: "foo", serverData, arch});
        await click(target.querySelector(".o_data_row td[name=name]"));
        // The value is selected after the click: right moves on at once
        await press("ArrowRight");
        assert.deepEqual(position(), ["qty", 0]);
        document.activeElement.setSelectionRange(1, 1);
        await press("ArrowRight");
        assert.deepEqual(position(), ["qty", 0], "cursor inside the text: stays");
        await press("ArrowLeft");
        assert.deepEqual(position(), ["qty", 0], "cursor not at the start: stays");
        document.activeElement.setSelectionRange(0, 0);
        await press("ArrowLeft");
        assert.deepEqual(position(), ["name", 0]);
    });

    QUnit.test("a multi-line text moves on only from its first or last character", async (assert) => {
        await makeView({type: "list", resModel: "foo", serverData, arch});
        await click(target.querySelector(".o_data_row td[name=note]"));
        document.activeElement.setSelectionRange(1, 1);
        await press("ArrowDown");
        assert.deepEqual(position(), ["note", 0]);
        document.activeElement.setSelectionRange(2, 2);
        await press("ArrowDown");
        assert.deepEqual(position(), ["note", 1]);
    });

    QUnit.test("a selection moves on with every arrow, its value unchanged", async (assert) => {
        await makeView({type: "list", resModel: "foo", serverData, arch});
        await click(target.querySelector(".o_data_row td[name=kind]"));
        assert.strictEqual(document.activeElement.tagName, "SELECT");
        await press("ArrowDown");
        assert.deepEqual(position(), ["kind", 1]);
        assert.strictEqual(document.activeElement.value, '"a"');
        await press("ArrowRight");
        assert.deepEqual(position(), ["email", 1]);
        await press("ArrowLeft");
        assert.deepEqual(position(), ["email", 1], "email: Left moves its text cursor");
        await press("ArrowUp");
        assert.deepEqual(position(), ["email", 0]);
    });

    QUnit.test("Enter on the last line still adds a line", async (assert) => {
        await makeView({type: "list", resModel: "foo", serverData, arch});
        await click(target.querySelectorAll(".o_data_row td[name=qty]")[2]);
        await press("Enter");
        assert.containsN(target, ".o_data_row", 4);
    });
});
