import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";
import vm from "node:vm";

class TestElement {
    constructor(tagName) {
        this.tagName = tagName;
        this.children = [];
        this.className = "";
        this.textContent = "";
        this.attributes = {};
        this.listeners = {};
        this.src = "";
        this.innerHTML = "";
    }

    addEventListener(name, listener) {
        this.listeners[name] = listener;
    }

    appendChild(child) {
        this.children.push(child);
        return child;
    }

    setAttribute(name, value) {
        this.attributes[name] = value;
    }
}

function thumbnailHarness() {
    const sourcePath = new URL("../src/app/app.js", import.meta.url);
    const source = fs.readFileSync(sourcePath, "utf8") + `
        globalThis.thumbnailTest = { missionThumbnail };
        globalThis.setThumbnailState = function setThumbnailState(value) { state = value; };
    `;
    const templates = {};
    for (const name of ["graduationcap", "matlab", "simulink"]) {
        templates["fallback-thumbnail-" + name] = {
            content: {
                cloneNode() {
                    const svg = new TestElement("svg");
                    svg.attributes.id = name;
                    return svg;
                }
            }
        };
    }
    const context = {
        window: {},
        document: {
            createElement(tagName) {
                return new TestElement(tagName);
            },
            getElementById(id) {
                return templates[id] || null;
            }
        }
    };
    vm.createContext(context);
    vm.runInContext(source, context);
    return context;
}

test("custom thumbnails bypass the generic three-logo treatment", () => {
    const context = thumbnailHarness();
    const thumbnail = context.thumbnailTest.missionThumbnail({
        Thumbnail: "data:image/png;base64,custom"
    });

    assert.equal(thumbnail.tagName, "img");
    assert.equal(thumbnail.className, "mission-thumbnail");
    assert.equal(thumbnail.src, "data:image/png;base64,custom");
    assert.equal(thumbnail.children.length, 0);
});

test("missing thumbnails render all three inline fallback logos", () => {
    const context = thumbnailHarness();
    const thumbnail = context.thumbnailTest.missionThumbnail({ Thumbnail: "" });
    const icons = thumbnail.children[0].children;

    assert.equal(thumbnail.className, "mission-thumbnail mission-thumbnail-fallback");
    assert.equal(icons.length, 3);
    assert.deepEqual(
        Array.from(icons, (icon) => icon.children[0].attributes.id),
        [
            "graduationcap",
            "matlab",
            "simulink"
        ]
    );
});

test("serialized empty custom thumbnails use the generic fallback", () => {
    const context = thumbnailHarness();
    const thumbnail = context.thumbnailTest.missionThumbnail({ Thumbnail: [""] });

    assert.equal(thumbnail.className, "mission-thumbnail mission-thumbnail-fallback");
});
