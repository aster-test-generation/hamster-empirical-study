import matplotlib.pyplot as plt

# Data: Distribution of testing frameworks (in percentages)
distribution_of_testing_framework = {
    "Spring-test": 2.91,
    "AssertJ": 13.26,
    "JUnit5": 26.69,
    "JUnit4": 26.07,
    "Mockito": 11.35,
    "JUnit3": 4.32,
    "Hamcrest": 4.02,
    "Powermock": 0.46,
    "Google-truth": 2.13,
    "TestNG": 6.31,
    "Androidx-test": 1.67,
    "Android-test": 0.02,
    "EasyMock": 0.45,
    "Rest-Assured": 0.25,
    "Spock": 0.02,
    "Cucumber": 0.09,
    "jMock": 0.01
}
# Group values below 1% into 'Other'
threshold = 1.0
grouped_data = {}
other_total = 0.0

for name, value in distribution_of_testing_framework.items():
    if value < threshold:
        other_total += value
    else:
        grouped_data[name] = value

if other_total > 0:
    grouped_data["Other (<1%)"] = other_total

sorted_items = sorted(grouped_data.items(), key=lambda item: item[1], reverse=True)
labels = []
sizes = []

# Prepare labels, appending percentage to last 3
for i, (label, value) in enumerate(sorted_items):
    sizes.append(value)
    if i >= len(sorted_items) - 3:
        labels.append(f"{label} ({value:.2f}%)")
    else:
        labels.append(label)

# Plot pie chart
plt.figure(figsize=(12, 12))
wedges, texts, autotexts = plt.pie(
    sizes,
    labels=labels,
    autopct=lambda pct: f'{pct:.1f}%' if pct >= 2 else '',  # show % only for slices >= 5%
    startangle=140,
    colors=plt.cm.Pastel1.colors,
    textprops={'fontsize': 20},
    wedgeprops={'edgecolor': 'black', 'linewidth': 1},
    labeldistance=1.05  # Move labels closer to the pie
)

plt.tight_layout()
plt.savefig('testing_framework.pdf', dpi=300, bbox_inches='tight')
