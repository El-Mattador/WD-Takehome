# Justification for Top-Down Hierarchical Classification

The **top-down hierarchical approach** was chosen after considering several factors: **accuracy, cost, latency, ease of implementation, explainability, and scalability**.

The Singapore mathematics syllabus is already organised as a hierarchy:

```
Strand → Sub-Strand → Topic → Learning Outcome
```

The classification pipeline mirrors this structure. Instead of selecting from all possible learning outcomes at once, the model first determines the **strand**, then the **sub-strand**, followed by the **topic**, and finally the **learning outcome**.

This design reduces the decision space at each step. For example, once a question is classified under **Measurement and Geometry**, the model no longer needs to consider learning outcomes under **Number and Algebra**. This narrowing of candidate labels makes the classification problem simpler for the model and improves interpretability.

This approach relies on the assumption that the syllabus hierarchy is **semantically well-structured**. In other words, each level logically implies the levels beneath it. For example:

* questions involving **angles** belong under **Geometry**
* **Geometry** is part of the strand **Measurement and Geometry**

Therefore, correctly identifying the higher-level category should significantly reduce the number of possible learning outcomes.

Another assumption is that the syllabus contains **well-defined and objective categories**. This means a human reader should generally be able to identify the correct learning outcome without ambiguity. If a question is ambiguous even to a human evaluator, it is unlikely that an LLM will classify it reliably.

---

# Prompt Optimizations

Several prompt optimizations were implemented to reduce **API cost and latency**.

The prompts were intentionally kept short, and the expected response format was simplified. Instead of returning full labels, the LLM was asked to return **only the index number of the selected option**. This reduces token usage and makes parsing the output easier.

Minimising prompt length also reduces the likelihood that the LLM deviates from the expected output schema. Because the model only needs to return a single number, the output is highly constrained and therefore more reliable.

---

# Limitations of the Hierarchical Approach

The main limitation of the top-down hierarchical design is the possibility of **cascading failure**.

If the model selects the wrong **strand**, it becomes impossible to recover the correct answer later in the pipeline because the correct sub-strand and learning outcomes will no longer be available as options.

For example, if a question about **money calculations** is mistakenly classified under **Number and Algebra** instead of **Measurement and Geometry**, the correct learning outcome cannot be selected in later stages.

The prompt optimizations and structural assumptions help reduce this risk, but they cannot eliminate it entirely.

---

# Observations from Error Analysis

After analysing the misclassified examples, several potential improvements were identified.

First, some questions contain **multiple-choice options**, which may provide useful contextual information. Including these options in the prompt could help the model better understand the type of concept being tested. However, this increases prompt length and API cost. It also introduces a dependency on the user supplying the answer options during manual input, which may reduce the flexibility of the system.

Second, inconsistencies were observed in the dataset. In one example, the **strand and sub-strand appear to contradict the syllabus structure**, suggesting the presence of noisy or incorrect labels. Designing prompts to explicitly account for such inconsistencies could reduce classification accuracy on cleaner data, so this case was not specifically handled in the current pipeline.

Third, some learning outcomes are **very similar to each other**. For example, questions related to multiplication tables could reasonably match more than one learning outcome. In such cases, a simple heuristic could improve consistency. For instance, if two candidate learning outcomes are highly similar, the model could select the one with the **lower topic reference number**, which often corresponds to the more general concept.

---

# Alternative Approaches

One alternative that could potentially improve performance is a **two-stage shortlist-then-selection approach**.

In this method, the LLM first generates a shortlist of the most relevant learning outcomes. In the second stage, the model selects the best answer from this smaller candidate set.

This approach offers several advantages:

* reduces the number of possible labels considered in the final decision
* avoids cascading failure caused by incorrect strand predictions
* removes the need to explicitly classify strand and sub-strand, which the error analysis showed may sometimes be misleading

Because the final decision is made across multiple candidate learning outcomes, the model has greater flexibility to correct earlier mistakes.

If the pipeline were redesigned, this approach would likely provide a better balance between **accuracy, cost, and robustness**.

---

# Ideal Approach with Unlimited Resources

If computational cost and engineering time were not constraints, the most robust solution would be a **retrieval-augmented classification system**.

In this design:

1. All syllabus learning outcomes would first be embedded into a vector space.
2. The question would also be embedded.
3. A retrieval step would identify the most semantically similar learning outcomes.
4. The LLM would then select the final classification from this retrieved shortlist.

This approach combines **semantic similarity search** with LLM reasoning, which reduces prompt size while maintaining flexibility in classification. It also scales well if the syllabus expands in the future.
