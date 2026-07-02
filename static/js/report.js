const circle = document.getElementById("score-circle");
const label = document.getElementById("score-label");
const score = parseInt(circle.dataset.score, 10) || 0;

let colorClasses;
let labelText;
let textColor;

if (score >= 80) {
    colorClasses = "border-emerald-500";
    textColor = "text-emerald-600";
    labelText = "Strong";
} else if (score >= 50) {
    colorClasses = "border-amber-500";
    textColor = "text-amber-600";
    labelText = "Needs improvement";
} else {
    colorClasses = "border-rose-500";
    textColor = "text-rose-600";
    labelText = "Poor";
}

circle.classList.add(colorClasses);
document.getElementById("score-number").classList.add(textColor);
label.textContent = labelText;
label.classList.add(textColor);
