"""Plain-language explanations of each kind of finding.

Every card in the Insights panel can open a details section with three short
paragraphs, shown as plain prose without headings: first exactly what was
measured and tested, with the thresholds the code applies, so the claim can
be checked; then what the pattern usually means physically; last, the common
ways the same pattern arises for other reasons and what to look at to tell
them apart.

The texts describe the method and its known pitfalls only. They never claim
more than the statistics support: a finding is a pattern in the data, and the
explanation says which causes are consistent with it, not which one is true.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Explanation:
    """The three paragraphs shown under a finding.

    Attributes:
        found: How the finding was detected.
        meaning: How to read it.
        check: What to verify before relying on it.
    """

    found: str
    meaning: str
    check: str


EXPLANATIONS: dict[str, Explanation] = {
    "interference": Explanation(
        found=(
            "For each measured mass m, the masses m+16 (oxide, MO⁺), m+17 (hydroxide, MOH⁺) "
            "and m/2 (doubly charged, M²⁺) were checked. A mass is flagged when at least 70 % "
            "of its detections arrive in particles that also carry the parent, the "
            "suspect-to-parent signal ratio is below 20 % with a robust spread under a factor "
            "of 2, and on log axes the two scale with a slope between 0.6 and 1.4."
        ),
        meaning=(
            "Oxide, hydroxide and doubly charged ions form in the plasma from the parent "
            "element itself, so their signal is a small, nearly fixed fraction of the parent's, "
            "particle by particle. A genuine second element at the same mass would vary on its "
            "own and would also appear in particles without the parent."
        ),
        check=(
            "Compare the ratio with the oxide or doubly charged ratio measured during tuning; "
            "it depends on nebuliser gas flow, RF power and sample loading. A real element at "
            "the same mass can sit on top of the interference, so look at particles that carry "
            "the suspect mass without the parent. Correct or exclude the mass before "
            "quantifying it."
        ),
    ),
    "isotope": Explanation(
        found=(
            "The ratio of the two isotopes' counts was computed in every particle carrying both. "
            "Only particles in the upper half of the more abundant isotope's signal were used: "
            "near the detection limit the minor isotope is only detected when it happens to read "
            "high, which would bias the ratio upward."
        ),
        meaning=(
            "Both masses belong to the same element, so their ratio describes the element's "
            "isotope signature, independently of how much of it a particle holds. These are raw "
            "count ratios, not corrected for mass bias."
        ),
        check=(
            "Counting statistics dominate single-particle ratios: with N counts on the minor "
            "isotope the relative uncertainty is about 1/√N, so individual particles scatter "
            "widely and medians over many particles are what can be compared. Correct for mass "
            "bias with a standard before comparing with literature values."
        ),
    ),
    "isotope_abundance": Explanation(
        found=(
            "The median ratio, from particles in the upper half of the major isotope's signal, "
            "was compared with the natural abundance ratio held in the app's periodic table. "
            "A card appears when the two differ by 25 % or more."
        ),
        meaning=(
            "Mass bias shifts measured ratios by a few percent, so a gap this large needs "
            "another cause: an isobaric or polyatomic interference adding signal to one "
            "isotope, a detection threshold that cuts the minor isotope, or a real isotopic "
            "difference such as an enriched tracer."
        ),
        check=(
            "Look for an interference card on either mass, and at the known interferences for "
            "both masses. Measure a standard of natural composition under the same conditions: "
            "if it shows the same gap, the cause is instrumental."
        ),
    ),
    "isotope_two": Explanation(
        found=(
            "The distribution of the log ratio was smoothed and searched for two peaks at least "
            "2.3 % apart, separated by a dip of at least 40 % below the lower peak, with the "
            "smaller group holding at least 10 % of the particles."
        ),
        meaning=(
            "Two ratio populations in one sample usually mean particles from two sources with "
            "different isotope signatures."
        ),
        check=(
            "Counting noise widens the ratio of small particles. If one population is made of "
            "small particles and the other of large ones, the split can come from counting "
            "statistics rather than from two sources: the ratio-against-signal panel shows this."
        ),
    ),
    "isotope_track": Explanation(
        found=(
            "For particles carrying both isotopes and another element, the rank correlation "
            "(Spearman) between the log ratio and the log signal of that element was tested. "
            "Isotopes of the same element were never used for this. The tests were corrected "
            "for false discovery and |ρ| had to reach 0.4."
        ),
        meaning=(
            "When an isotope ratio rises or falls with a different element, the particles "
            "likely mix two sources: one whose isotope signature comes with that element and "
            "one without it."
        ),
        check=(
            "A trend can also appear if the other element grows with particle size and the "
            "ratio is biased at small signals by counting statistics. Check that the trend "
            "holds among large particles, and that the other element does not interfere with "
            "either isotope."
        ),
    ),
    "isotope_groups": Explanation(
        found=(
            "Each replicate's median ratio was taken as one observation. With every group "
            "replicated the groups were compared by one-way ANOVA on those medians; otherwise "
            "by Kruskal-Wallis on particle ratios. The difference had to be at least 2 % and "
            "more than twice the spread between replicates, after false discovery correction."
        ),
        meaning=(
            "Both masses are isotopes of one element, so the groups differ in isotope "
            "signature rather than in amount, which points to different sources."
        ),
        check=(
            "Mass bias can drift between sessions. If the groups were measured on different "
            "days, bracket them with the same standard before trusting a difference of a few "
            "percent."
        ),
    ),
    "comparison": Explanation(
        found=(
            "Groups of replicates were compared, never replicates of one material against each "
            "other. With every group replicated, the replicate medians were compared by one-way "
            "ANOVA; otherwise the particles of each group by Kruskal-Wallis. The difference had "
            "to reach a factor of 1.5 and exceed twice the spread between replicates, after "
            "false discovery correction across elements."
        ),
        meaning=(
            "Particles of one group carry more of the element than those of the other."
        ),
        check=(
            "Counts depend on sensitivity. If the groups were measured in different sessions or "
            "with different transport efficiency, compare masses rather than counts. This is a "
            "comparison per particle, not of particle number concentration."
        ),
    ),
    "signature": Explanation(
        found=(
            "The share of particles carrying the element (or the combination) was averaged over "
            "each group's replicates and compared between groups with Fisher's exact test, "
            "corrected for false discovery. The gap had to be at least 15 points and more than "
            "twice the spread between replicates."
        ),
        meaning=(
            "The element marks one group: it is found in that group's particles and rarely or "
            "never in the other's."
        ),
        check=(
            "An element can look absent when its particles are below the detection limit. "
            "Compare the detection thresholds of the two groups before reading absence as a "
            "real difference."
        ),
    ),
    "replicate_flag": Explanation(
        found=(
            "Each replicate was summarised by its particle arrival rate and by the median signal "
            "and detection rate of the group's main elements. With three or more replicates, one "
            "is flagged when it sits more than ×1.5 (or 15 points) away from the others while "
            "they agree among themselves. With two, only the disagreement can be reported."
        ),
        meaning=(
            "One replicate does not look like the others; pooling it would hide the difference."
        ),
        check=(
            "Typical causes are contamination, a partly blocked nebuliser or cones, a dilution "
            "error, or drift during the run. Its timeline usually shows which."
        ),
    ),
    "replicate_agree": Explanation(
        found=(
            "No replicate differed from the others by more than ×1.5 in median signal or 15 "
            "points in detection rate on the group's main elements, nor in particle arrival "
            "rate."
        ),
        meaning=(
            "The replicates are consistent, so differences between this group and others larger "
            "than the spread shown can be attributed to the samples rather than to the "
            "measurement."
        ),
        check="Agreement is judged on the main elements only; minor elements are not covered.",
    ),
    "stoichiometry": Explanation(
        found=(
            "In particles carrying both elements, the robust spread of the log ratio was "
            "compared with the spread expected if the elements varied independently. A pair is "
            "reported when the ratio's spread is under a factor of about 1.6 and below 40 % of "
            "that independent spread."
        ),
        meaning=(
            "A ratio that holds while the amounts vary over orders of magnitude suggests one "
            "phase of fixed composition. With molar amounts, a ratio close to a small whole "
            "number ratio can be read as a formula."
        ),
        check=(
            "Moles depend on the calibration of both elements; an error in either shifts the "
            "ratio but not its tightness. Compare with a reference material of known "
            "composition if available."
        ),
    ),
    "correlation": Explanation(
        found=(
            "Rank correlation (Spearman) between two different elements in particles carrying "
            "both, with Pearson on log values alongside. All pairs were tested and corrected for "
            "false discovery; |ρ| had to reach 0.5. Isotopes of one element and interference "
            "pairs are excluded."
        ),
        meaning=(
            "The two elements rise and fall together. The proportionality coefficient ρp says "
            "whether their ratio is fixed (near 1) or whether they only grow together with "
            "particle size (low)."
        ),
        check=(
            "Correlation only uses particles carrying both elements; it says nothing about "
            "particles carrying one of them."
        ),
    ),
    "network": Explanation(
        found=(
            "Every pair of frequently detected elements was correlated as for a correlation "
            "card, and significant pairs with |ρ| ≥ 0.5 were linked into a graph. The largest "
            "connected group of four or more elements is reported."
        ),
        meaning="Elements linked this way often come from one source or one particle type.",
        check="Links are pairwise; two elements in the group need not correlate directly.",
    ),
    "cooccurrence_with": Explanation(
        found=(
            "Presence only, not amount. The rarer element must come with the other in at least "
            "80 % of its particles, at least 1.5 times more often than chance, confirmed by "
            "Fisher's exact test with false discovery correction."
        ),
        meaning="The two elements belong to the same particles: likely one phase or one source.",
        check=(
            "If the other element is detected in most particles anyway, co-occurrence is less "
            "informative; the lift value says how far above chance it is."
        ),
    ),
    "cooccurrence_avoid": Explanation(
        found=(
            "Presence only. Far fewer particles carry both elements than chance predicts (at "
            "most a quarter of the expected number), confirmed by Fisher's exact test with false "
            "discovery correction."
        ),
        meaning="The elements sit in different particle populations.",
        check=(
            "If one element is only detectable in large particles, it will seem to avoid "
            "elements found mostly in small ones; compare their size distributions."
        ),
    ),
    "rare": Explanation(
        found=(
            "Elements detected in only a handful of particles, listed with the elements found in "
            "at least half of those particles and at least twice as often as in the whole sample."
        ),
        meaning="A few distinct particles can be a real minor phase or a contamination event.",
        check=(
            "With so few particles, check each one: whether they arrive together in time "
            "(a burst) and whether the counts are well above the detection threshold."
        ),
    ),
    "quality": Explanation(
        found=(
            "The distribution of the element's values (size, then mass, then counts) peaks in "
            "its lowest bins, with at least 15 % of particles in the bottom 5 % of the log range."
        ),
        meaning=(
            "The population continues below what can be detected, so only its upper part is "
            "measured: means and medians are biased upward and particle numbers underestimated."
        ),
        check=(
            "Compare the lowest values with the detection threshold shown in the figure. Size "
            "and mass detection limits scale with the counts threshold through the calibration."
        ),
    ),
    "time_rate": Explanation(
        found=(
            "Particle arrivals were counted in 20 equal time bins and tested against a steady "
            "Poisson process (χ²). A trend in those counts (Spearman |ρ| ≥ 0.7, change of ×1.3 "
            "or more) is reported as drift; scatter without a trend as bursts."
        ),
        meaning=(
            "A drifting rate points to a change in sample transport during the run; bursts to "
            "agglomerates, droplets or contamination events."
        ),
        check=(
            "Particle number concentrations from this sample depend on the transport rate; "
            "check the uptake and the nebuliser, and re-run if the drift is large."
        ),
    ),
    "time_signal": Explanation(
        found=(
            "The median signal of the main elements was followed over ten time bins; a steady "
            "trend (Spearman |ρ| ≥ 0.8, p < 0.01) of at least ×1.25 from start to end is "
            "reported."
        ),
        meaning=(
            "Several elements drifting together point to a change in instrument sensitivity; "
            "one element alone points to the particles themselves changing, for example "
            "dissolving or settling."
        ),
        check="Sensitivity drift can be checked with an internal standard or a repeated standard.",
    ),
    "size": Explanation(
        found=(
            "In multi-element particles, the element's mass fraction was ranked against total "
            "particle mass (Spearman), corrected for false discovery; |ρ| had to reach 0.3."
        ),
        meaning=(
            "A share that falls with size fits a coating, shell or surface-bound element, which "
            "thins out as particles grow; a share that rises fits a core."
        ),
        check=(
            "Small particles near the detection limit lose their minor elements first, which "
            "can create the same trend; check that it holds well above the detection limit."
        ),
    ),
    "distribution_two": Explanation(
        found=(
            "Values were searched on a log scale for two peaks at least a factor of 2 apart, "
            "separated by a dip at least 40 % below the lower peak, with at least 10 % of "
            "particles in the smaller group."
        ),
        meaning="Two size or mass populations of the same element, often two particle types.",
        check=(
            "A lower population that sits right on the detection threshold may be noise or "
            "dissolved signal rather than particles."
        ),
    ),
    "distribution_spread": Explanation(
        found="Elements ranked by the coefficient of variation of their detected values.",
        meaning="Values differ widely from particle to particle; a mean alone hides this.",
        check="A long tail is normal for particle sizes; look at the shape, not only the spread.",
    ),
    "outlier": Explanation(
        found=(
            "On log values, particles more than 3 interquartile ranges above the upper quartile "
            "(single element), or more than 3.5 robust z-scores above the median in two elements "
            "at once (joint outliers)."
        ),
        meaning=(
            "Particles far larger than the rest; being extreme in two elements at once is much "
            "less likely to be chance than a single long tail."
        ),
        check="Check for coincident events (two particles arriving together) and for saturation.",
    ),
    "composition": Explanation(
        found=(
            "Counts of particles by the set of elements detected in them, and the share of "
            "multi-element particles per element."
        ),
        meaning="Which particle types dominate, and which elements occur alone or in mixtures.",
        check=(
            "Which elements are detected in a particle depends on each element's detection "
            "limit; small particles may lose their minor elements."
        ),
    ),
}
"""Explanations keyed by a finding's ``explain_key`` (or its category)."""


def explanation_for(key: str, category: str = "") -> Explanation | None:
    """Return the explanation for a finding.

    Args:
        key: The finding's explain key.
        category: Its category, used when the key has no entry.

    Returns:
        The :class:`Explanation`, or ``None``.
    """
    return EXPLANATIONS.get(key) or EXPLANATIONS.get(category)
