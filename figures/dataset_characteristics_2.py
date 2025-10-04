import matplotlib.pyplot as plt

# Data: Distribution of testing frameworks (in percentages)
distribution_of_testing_framework = {
    "Java SE": 53.492063492063494,
    "Android": 12.380952380952381,
    "Web API": 20.158730158730158,
    "Web Application": 8.253968253968253,
    "Java EE": 5.714285714285714
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
plt.savefig('application_type.pdf', dpi=300, bbox_inches='tight')
