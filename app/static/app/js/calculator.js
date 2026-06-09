document.addEventListener("DOMContentLoaded", () => {
    const expressionInput = document.getElementById("calculator-expression");
    const preview = document.getElementById("calculator-preview");
    const historyContainer = document.getElementById("calculator-history");
    const clearHistoryButton = document.getElementById("calculator-clear-history");
    const angleLabel = document.getElementById("calculator-angle-label");
    const memoryLabel = document.getElementById("calculator-memory-label");
    const modeButtons = document.querySelectorAll("[data-angle-mode]");
    const keys = document.querySelectorAll(".calc-key");
    const exampleButtons = document.querySelectorAll("[data-example]");

    if (!expressionInput || !preview) {
        return;
    }

    const HISTORY_KEY = "mytools_scientific_calculator_history";
    const MEMORY_KEY = "mytools_scientific_calculator_memory";
    const ANSWER_KEY = "mytools_scientific_calculator_answer";
    const MODE_KEY = "mytools_scientific_calculator_angle_mode";
    const labels = {
        ready: "Bereit",
        emptyHistory: "Noch keine Rechnungen.",
        enterExpression: "Gib zuerst eine Rechnung ein.",
        nonFinite: "Das Ergebnis ist nicht endlich.",
        unexpectedToken: "Unerwartetes Zeichen.",
        parseIncomplete: "Der Ausdruck konnte nicht vollständig gelesen werden.",
        missingValue: "Hier fehlt eine Zahl oder Funktion.",
        divisionByZero: "Division durch 0 ist nicht möglich.",
        negativeRoot: "Wurzel aus negativer Zahl ist hier nicht möglich.",
        lnPositive: "ln braucht eine Zahl größer 0.",
        logPositive: "log braucht eine Zahl größer 0.",
        logbaseInvalid: "logbase braucht gültige Werte und Basis ungleich 1.",
        factorialInteger: "Fakultät geht nur mit ganzen Zahlen ab 0.",
        factorialLarge: "Fakultät ist zu groß für diesen Rechner.",
        rootZero: "Die Wurzelordnung darf nicht 0 sein.",
        evenNegativeRoot: "Gerade Wurzeln aus negativen Zahlen sind nicht möglich.",
        invalidCalculation: "Ungültige Rechnung.",
        doubleDecimal: "Eine Zahl enthält zwei Dezimalpunkte.",
        expNeedsNumber: "EXP braucht eine Zahl als Exponent.",
        invalidNumber: "Ungültige Zahl.",
        unknownCharacter: "Unbekanntes Zeichen: {value}",
        expectedValues: "{name} erwartet {count} Wert(e).",
        unknownFunction: "Unbekannte Funktion: {name}",
        unknownConstant: "Unbekannte Konstante: {name}",
        ...(window.MyToolsCalculatorI18n || {}),
    };

    const translate = (key, replacements = {}) => Object.entries(replacements).reduce(
        (text, [name, value]) => text.replace(`{${name}}`, value),
        labels[key] || key,
    );

    const coarsePointerQuery = typeof window.matchMedia === "function"
        ? window.matchMedia("(hover: none), (pointer: coarse)")
        : null;

    function isTouchKeypadMode() {
        return Boolean(coarsePointerQuery?.matches);
    }

    function focusExpression({ force = false } = {}) {
        if (!force && isTouchKeypadMode()) {
            return;
        }

        const scrollX = window.scrollX;
        const scrollY = window.scrollY;
        try {
            expressionInput.focus({ preventScroll: true });
        } catch (error) {
            focusExpression();
            window.scrollTo(scrollX, scrollY);
        }
    }

    function getExpressionRange() {
        const fallbackPosition = expressionInput.value.length;
        if (isTouchKeypadMode() && document.activeElement !== expressionInput) {
            return { start: fallbackPosition, end: fallbackPosition };
        }

        const start = Number.isInteger(expressionInput.selectionStart)
            ? expressionInput.selectionStart
            : fallbackPosition;
        const end = Number.isInteger(expressionInput.selectionEnd)
            ? expressionInput.selectionEnd
            : fallbackPosition;
        return { start, end };
    }

    function setExpressionCursor(position) {
        const nextPosition = Math.max(0, Math.min(position, expressionInput.value.length));
        try {
            expressionInput.setSelectionRange(nextPosition, nextPosition);
        } catch (error) {
            // Einige mobile Browser erlauben setSelectionRange nur bei fokussierten Feldern.
        }
    }

    let angleMode = localStorage.getItem(MODE_KEY) || "deg";
    let memory = Number.parseFloat(localStorage.getItem(MEMORY_KEY) || "0") || 0;
    let lastAnswer = Number.parseFloat(localStorage.getItem(ANSWER_KEY) || "0") || 0;
    let history = loadHistory();

    class CalculatorError extends Error {}

    class Parser {
        constructor(tokens) {
            this.tokens = tokens;
            this.position = 0;
        }

        current() {
            return this.tokens[this.position] || { type: "eof", value: "" };
        }

        consume(type, value = null) {
            const token = this.current();
            if (token.type !== type || (value !== null && token.value !== value)) {
                throw new CalculatorError(translate("unexpectedToken"));
            }
            this.position += 1;
            return token;
        }

        match(type, value = null) {
            const token = this.current();
            if (token.type === type && (value === null || token.value === value)) {
                this.position += 1;
                return true;
            }
            return false;
        }

        parse() {
            const value = this.parseAdditive();
            if (this.current().type !== "eof") {
                throw new CalculatorError(translate("parseIncomplete"));
            }
            return value;
        }

        parseAdditive() {
            let value = this.parseMultiplicative();
            while (true) {
                if (this.match("operator", "+")) {
                    value += this.parseMultiplicative();
                } else if (this.match("operator", "-")) {
                    value -= this.parseMultiplicative();
                } else {
                    return value;
                }
            }
        }

        parseMultiplicative() {
            let value = this.parsePower();
            while (true) {
                if (this.match("operator", "*")) {
                    value *= this.parsePower();
                } else if (this.match("operator", "/")) {
                    const divisor = this.parsePower();
                    if (divisor === 0) {
                        throw new CalculatorError(translate("divisionByZero"));
                    }
                    value /= divisor;
                } else {
                    return value;
                }
            }
        }

        parsePower() {
            let value = this.parseUnary();
            if (this.match("operator", "^")) {
                value = Math.pow(value, this.parsePower());
            }
            return value;
        }

        parseUnary() {
            if (this.match("operator", "+")) {
                return this.parseUnary();
            }
            if (this.match("operator", "-")) {
                return -this.parseUnary();
            }
            return this.parsePostfix();
        }

        parsePostfix() {
            let value = this.parsePrimary();
            while (true) {
                if (this.match("operator", "!")) {
                    value = factorial(value);
                } else if (this.match("operator", "%")) {
                    value /= 100;
                } else {
                    return value;
                }
            }
        }

        parsePrimary() {
            const token = this.current();

            if (this.match("number")) {
                return token.value;
            }

            if (this.match("identifier")) {
                const name = token.value.toLowerCase();
                if (this.match("paren", "(")) {
                    const args = [];
                    if (!this.match("paren", ")")) {
                        do {
                            args.push(this.parseAdditive());
                        } while (this.match("comma"));
                        this.consume("paren", ")");
                    }
                    return applyFunction(name, args);
                }
                return getConstant(name);
            }

            if (this.match("paren", "(")) {
                const value = this.parseAdditive();
                this.consume("paren", ")");
                return value;
            }

            throw new CalculatorError(translate("missingValue"));
        }
    }

    function normalizeExpression(expression) {
        return expression
            .replace(/×/g, "*")
            .replace(/÷/g, "/")
            .replace(/−/g, "-")
            .replace(/π/g, "pi")
            .replace(/√/g, "sqrt")
            .replace(/Ans/g, "ans")
            .replace(/,/g, ",");
    }

    function tokenize(expression) {
        const normalized = normalizeExpression(expression);
        const tokens = [];
        let index = 0;

        while (index < normalized.length) {
            const char = normalized[index];

            if (/\s/.test(char)) {
                index += 1;
                continue;
            }

            if (/[0-9.]/.test(char)) {
                let numberText = "";
                let hasDecimal = false;

                while (index < normalized.length) {
                    const current = normalized[index];
                    if (/[0-9]/.test(current)) {
                        numberText += current;
                        index += 1;
                        continue;
                    }
                    if (current === ".") {
                        if (hasDecimal) {
                            throw new CalculatorError(translate("doubleDecimal"));
                        }
                        hasDecimal = true;
                        numberText += current;
                        index += 1;
                        continue;
                    }
                    break;
                }

                if (index < normalized.length && /[eE]/.test(normalized[index])) {
                    numberText += "e";
                    index += 1;
                    if (index < normalized.length && /[+-]/.test(normalized[index])) {
                        numberText += normalized[index];
                        index += 1;
                    }
                    let exponentDigits = "";
                    while (index < normalized.length && /[0-9]/.test(normalized[index])) {
                        exponentDigits += normalized[index];
                        index += 1;
                    }
                    if (!exponentDigits) {
                        throw new CalculatorError(translate("expNeedsNumber"));
                    }
                    numberText += exponentDigits;
                }

                const value = Number.parseFloat(numberText);
                if (!Number.isFinite(value)) {
                    throw new CalculatorError(translate("invalidNumber"));
                }
                tokens.push({ type: "number", value });
                continue;
            }

            if (/[a-zA-Z]/.test(char)) {
                let name = "";
                while (index < normalized.length && /[a-zA-Z]/.test(normalized[index])) {
                    name += normalized[index];
                    index += 1;
                }
                tokens.push({ type: "identifier", value: name });
                continue;
            }

            if ("+-*/^%!".includes(char)) {
                tokens.push({ type: "operator", value: char });
                index += 1;
                continue;
            }

            if (char === "(" || char === ")") {
                tokens.push({ type: "paren", value: char });
                index += 1;
                continue;
            }

            if (char === ",") {
                tokens.push({ type: "comma", value: char });
                index += 1;
                continue;
            }

            throw new CalculatorError(translate("unknownCharacter", { value: char }));
        }

        tokens.push({ type: "eof", value: "" });
        return tokens;
    }

    function evaluate(expression) {
        const cleanExpression = expression.trim();
        if (!cleanExpression) {
            throw new CalculatorError(translate("enterExpression"));
        }
        const parser = new Parser(tokenize(cleanExpression));
        const result = parser.parse();
        if (!Number.isFinite(result)) {
            throw new CalculatorError(translate("nonFinite"));
        }
        return result;
    }

    function applyFunction(name, args) {
        const need = (count) => {
            if (args.length !== count) {
                throw new CalculatorError(translate("expectedValues", { name, count }));
            }
        };

        switch (name) {
            case "sin":
                need(1);
                return Math.sin(toRadians(args[0]));
            case "cos":
                need(1);
                return Math.cos(toRadians(args[0]));
            case "tan":
                need(1);
                return Math.tan(toRadians(args[0]));
            case "asin":
                need(1);
                return fromRadians(Math.asin(args[0]));
            case "acos":
                need(1);
                return fromRadians(Math.acos(args[0]));
            case "atan":
                need(1);
                return fromRadians(Math.atan(args[0]));
            case "sqrt":
                need(1);
                if (args[0] < 0) throw new CalculatorError(translate("negativeRoot"));
                return Math.sqrt(args[0]);
            case "cbrt":
                need(1);
                return Math.cbrt(args[0]);
            case "root":
                need(2);
                return nthRoot(args[0], args[1]);
            case "ln":
                need(1);
                if (args[0] <= 0) throw new CalculatorError(translate("lnPositive"));
                return Math.log(args[0]);
            case "log":
                need(1);
                if (args[0] <= 0) throw new CalculatorError(translate("logPositive"));
                return Math.log10(args[0]);
            case "logbase":
                need(2);
                if (args[0] <= 0 || args[1] <= 0 || args[1] === 1) {
                    throw new CalculatorError(translate("logbaseInvalid"));
                }
                return Math.log(args[0]) / Math.log(args[1]);
            case "exp":
                need(1);
                return Math.exp(args[0]);
            case "abs":
                need(1);
                return Math.abs(args[0]);
            case "round":
                need(1);
                return Math.round(args[0]);
            case "floor":
                need(1);
                return Math.floor(args[0]);
            case "ceil":
                need(1);
                return Math.ceil(args[0]);
            default:
                throw new CalculatorError(translate("unknownFunction", { name }));
        }
    }

    function getConstant(name) {
        switch (name) {
            case "pi":
                return Math.PI;
            case "e":
                return Math.E;
            case "ans":
                return lastAnswer;
            default:
                throw new CalculatorError(translate("unknownConstant", { name }));
        }
    }

    function factorial(value) {
        if (!Number.isInteger(value) || value < 0) {
            throw new CalculatorError(translate("factorialInteger"));
        }
        if (value > 170) {
            throw new CalculatorError(translate("factorialLarge"));
        }
        let result = 1;
        for (let i = 2; i <= value; i += 1) {
            result *= i;
        }
        return result;
    }

    function nthRoot(value, degree) {
        if (degree === 0) {
            throw new CalculatorError(translate("rootZero"));
        }
        if (value < 0 && Math.abs(degree % 2) !== 1) {
            throw new CalculatorError(translate("evenNegativeRoot"));
        }
        const sign = value < 0 ? -1 : 1;
        return sign * Math.pow(Math.abs(value), 1 / degree);
    }

    function toRadians(value) {
        return angleMode === "deg" ? value * Math.PI / 180 : value;
    }

    function fromRadians(value) {
        return angleMode === "deg" ? value * 180 / Math.PI : value;
    }

    function formatResult(value) {
        if (!Number.isFinite(value)) {
            return "-";
        }
        const normalized = Math.abs(value) < 1e-12 ? 0 : value;
        const absolute = Math.abs(normalized);

        if ((absolute !== 0 && absolute < 0.000001) || absolute >= 1e12) {
            return normalized.toExponential(10).replace(/\.0+e/, "e").replace(/(\.\d*?)0+e/, "$1e");
        }

        return new Intl.NumberFormat("de-DE", {
            maximumFractionDigits: 12,
        }).format(normalized);
    }

    function insertText(text) {
        const { start, end } = getExpressionRange();
        const value = expressionInput.value;
        expressionInput.value = `${value.slice(0, start)}${text}${value.slice(end)}`;
        const nextPosition = start + text.length;
        focusExpression();
        setExpressionCursor(nextPosition);
        updatePreview();
    }

    function wrapCurrentExpression(prefix, suffix = ")") {
        const value = expressionInput.value.trim();
        expressionInput.value = value ? `${prefix}${value}${suffix}` : `${prefix}${suffix}`;
        focusExpression();
        setExpressionCursor(expressionInput.value.length - suffix.length);
        updatePreview();
    }

    function calculate({ pushHistory = true } = {}) {
        const expression = expressionInput.value.trim();
        try {
            const result = evaluate(expression);
            lastAnswer = result;
            localStorage.setItem(ANSWER_KEY, String(result));
            preview.textContent = `= ${formatResult(result)}`;
            preview.classList.remove("is-error");
            if (pushHistory) {
                addHistory(expression, result);
            }
            return result;
        } catch (error) {
            preview.textContent = error instanceof CalculatorError ? error.message : translate("invalidCalculation");
            preview.classList.add("is-error");
            return null;
        }
    }

    function updatePreview() {
        const expression = expressionInput.value.trim();
        if (!expression) {
            preview.textContent = translate("ready");
            preview.classList.remove("is-error");
            return;
        }

        try {
            const result = evaluate(expression);
            preview.textContent = `≈ ${formatResult(result)}`;
            preview.classList.remove("is-error");
        } catch (error) {
            preview.textContent = "…";
            preview.classList.remove("is-error");
        }
    }

    function loadHistory() {
        try {
            const parsed = JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]");
            return Array.isArray(parsed) ? parsed.slice(0, 12) : [];
        } catch (error) {
            return [];
        }
    }

    function saveHistory() {
        localStorage.setItem(HISTORY_KEY, JSON.stringify(history.slice(0, 12)));
    }

    function addHistory(expression, result) {
        history = [
            {
                expression,
                result,
                displayResult: formatResult(result),
                createdAt: Date.now(),
            },
            ...history.filter((item) => item.expression !== expression),
        ].slice(0, 12);
        saveHistory();
        renderHistory();
    }

    function renderHistory() {
        if (!historyContainer) {
            return;
        }

        historyContainer.innerHTML = "";
        if (!history.length) {
            const empty = document.createElement("div");
            empty.className = "calculator-empty-history";
            empty.textContent = translate("emptyHistory");
            historyContainer.appendChild(empty);
            return;
        }

        history.forEach((item) => {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "calculator-history-item";
            button.innerHTML = `<span></span><strong></strong>`;
            button.querySelector("span").textContent = item.expression;
            button.querySelector("strong").textContent = `= ${item.displayResult}`;
            button.addEventListener("click", () => {
                expressionInput.value = item.expression;
                focusExpression();
                updatePreview();
            });
            historyContainer.appendChild(button);
        });
    }

    function updateMemoryUi() {
        if (!memoryLabel) {
            return;
        }
        memoryLabel.classList.toggle("is-hidden", memory === 0);
    }

    function setAngleMode(mode) {
        angleMode = mode === "rad" ? "rad" : "deg";
        localStorage.setItem(MODE_KEY, angleMode);
        modeButtons.forEach((button) => {
            button.classList.toggle("active", button.dataset.angleMode === angleMode);
        });
        if (angleLabel) {
            angleLabel.textContent = angleMode.toUpperCase();
        }
        updatePreview();
    }

    function flashKeyByText(text) {
        const key = Array.from(keys).find((button) => button.dataset.insert === text || button.textContent.trim() === text);
        if (!key) return;
        key.classList.add("is-pressed");
        window.setTimeout(() => key.classList.remove("is-pressed"), 110);
    }

    keys.forEach((key) => {
        key.addEventListener("click", () => {
            const action = key.dataset.action;
            const insert = key.dataset.insert;

            if (insert !== undefined) {
                insertText(insert);
                return;
            }

            switch (action) {
                case "calculate":
                    calculate();
                    break;
                case "clear":
                    expressionInput.value = "";
                    updatePreview();
                    focusExpression();
                    break;
                case "backspace": {
                    const { start, end } = getExpressionRange();
                    if (start !== end) {
                        expressionInput.value = `${expressionInput.value.slice(0, start)}${expressionInput.value.slice(end)}`;
                        setExpressionCursor(start);
                    } else if (start > 0) {
                        expressionInput.value = `${expressionInput.value.slice(0, start - 1)}${expressionInput.value.slice(start)}`;
                        setExpressionCursor(start - 1);
                    }
                    updatePreview();
                    focusExpression();
                    break;
                }
                case "square":
                    insertText("^2");
                    break;
                case "cube":
                    insertText("^3");
                    break;
                case "reciprocal":
                    wrapCurrentExpression("1/(");
                    break;
                case "insert-answer":
                    insertText("ans");
                    break;
                case "memory-clear":
                    memory = 0;
                    localStorage.setItem(MEMORY_KEY, "0");
                    updateMemoryUi();
                    break;
                case "memory-recall":
                    insertText(String(memory));
                    break;
                case "memory-add": {
                    const value = calculate({ pushHistory: false });
                    if (value !== null) {
                        memory += value;
                        localStorage.setItem(MEMORY_KEY, String(memory));
                        updateMemoryUi();
                    }
                    break;
                }
                case "memory-subtract": {
                    const value = calculate({ pushHistory: false });
                    if (value !== null) {
                        memory -= value;
                        localStorage.setItem(MEMORY_KEY, String(memory));
                        updateMemoryUi();
                    }
                    break;
                }
                default:
                    break;
            }
        });
    });

    modeButtons.forEach((button) => {
        button.addEventListener("click", () => setAngleMode(button.dataset.angleMode));
    });

    exampleButtons.forEach((button) => {
        button.addEventListener("click", () => {
            expressionInput.value = button.dataset.example || "";
            focusExpression();
            updatePreview();
        });
    });

    if (clearHistoryButton) {
        clearHistoryButton.addEventListener("click", () => {
            history = [];
            saveHistory();
            renderHistory();
        });
    }

    expressionInput.addEventListener("input", updatePreview);

    expressionInput.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            calculate();
            return;
        }
        if (event.key === "Escape") {
            event.preventDefault();
            expressionInput.value = "";
            updatePreview();
            return;
        }
        if (event.key === "*") flashKeyByText("*");
        if (event.key === "/") flashKeyByText("/");
    });

    document.addEventListener("keydown", (event) => {
        const tagName = document.activeElement?.tagName?.toLowerCase();
        if (tagName === "input" || tagName === "textarea" || tagName === "select") {
            return;
        }

        if (/^[0-9.+\-*/^(),%!eE]$/.test(event.key)) {
            event.preventDefault();
            insertText(event.key);
        } else if (event.key === "Enter") {
            event.preventDefault();
            calculate();
        } else if (event.key === "Backspace") {
            event.preventDefault();
            focusExpression({ force: true });
        }
    });

    window.MyToolsCalculator = {
        evaluate,
        formatResult,
        setAngleMode,
    };

    setAngleMode(angleMode);
    updateMemoryUi();
    renderHistory();
    updatePreview();
});
