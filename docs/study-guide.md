# Study guide for Black Hole Flight Lab

To understand whole build, study **physics, numerical simulation, machine learning, control, verification, computer graphics, and experiment design**.

First, separate two AI systems we built:

- **Original experiment:** neural network learns gravitational potential, then predicts escape.
- **Current pilot:** AI learns possible engine-burn plans.
  Written physics equations score those plans.
- **Cockpit:** renders calculated flight and handles walking.
  Its visuals come from geometry and shaders.

Current pilot’s loop: **observe state, generate plans, simulate them, choose one, execute first burn, repeat.**

This is study map, roughly in prerequisite order:

| Topic | What to study | Where it appears |
|---|---|---|
| **1. Scientific programming** | Python, NumPy arrays, shapes, broadcasting, vectorization, functions, testing | Represents spacecraft states and simulates many candidate plans together |
| **2. Linear algebra** | Vectors, matrices, dot products, norms, coordinate bases, rotations | Neural networks, acceleration components, camera movement, 3D geometry |
| **3. Calculus and differential equations** | Derivatives, partial derivatives, gradients, chain rule, integration, initial-value problems | Equations describe how position, motion, and fuel change |
| **4. Probability and statistics** | Gaussian noise, sampling, expectation, variance, mean squared error, confidence intervals | Diffusion generation, training losses, uncertainty in experimental results |
| **5. Classical mechanics** | Position and velocity, forces, torque, energy, angular momentum, effective potentials, phase space | Foundation for understanding trajectories and engine burns |
| **6. Relativity** | Proper time, spacetime metrics, four-vectors, Lorentz transformations, geodesics, Schwarzschild geometry, geometric units | Defines spacecraft motion and light bending near black hole |
| **7. Numerical analysis** | Floating-point error, cancellation, Runge–Kutta methods, adaptive integration, event detection, convergence | Converts equations into computed trajectories without silently trusting inaccurate answers |
| **8. Neural-network fundamentals** | Supervised learning, backpropagation, gradient descent, normalization, overfitting, validation, class imbalance | Trains both learned potential and learned pilot components |
| **9. Learned world models** | Learning dynamics or potentials, conservation laws, derivatives of learned functions, model error, distribution shift | Original experiment tests whether convincing learned physics gives correct escape decisions |
| **10. Planning and control** | State/action representations, trajectory optimization, shooting methods, feedback, constraints, model predictive control | Scores future burn sequences, executes one command, then replans |
| **11. Imitation learning** | Expert demonstrations, behavior cloning, teacher quality, coverage of training states | Classical planner supplies training examples for AI pilot |
| **12. Autoencoders** | Encoders, decoders, latent representations, reconstruction loss, information bottlenecks | Compresses 24 burn-command values into eight latent values |
| **13. Transformers** | Tokens, embeddings, queries/keys/values, attention, residual connections, normalization, conditioning | Predicts noise in compressed burn plans using spacecraft state |
| **14. Diffusion models** | Forward noise process, noise prediction, schedules, conditional generation, reverse sampling, DDIM, latent diffusion | Converts random noise into several possible burn plans |
| **15. Verification** | Invariants, property tests, exact arithmetic, polynomial roots, Sturm’s theorem, certificates, trusted computing base | Original experiment checks escape claims with exact rational algebra |
| **16. Experimental science for AI** | Baselines, ablations, paired comparisons, train/validation/test separation, stress tests, seeds, compute fairness, post hoc analysis | Establishes whether learning helps and whether claimed improvements survive simpler comparisons |
| **17. Real-time graphics** | Meshes, scene graphs, camera projection, quaternions, rasterization, ray tracing, GLSL, materials, textures, shadows, HDR, bloom | Produces cockpit and black-hole view |
| **18. Interactive simulation** | Input events, animation loops, time steps, collision detection, swept bounding boxes, camera versus body movement | Explains floating controls, grounded walking, furniture collision, and frame pacing |
| **19. Systems and reproducibility** | HTTP/JSON, asynchronous requests, checkpoints, hashes, manifests, deterministic seeds, model export, numerical parity | Connects browser to simulator and keeps experiments reproducible across runs |
| **20. Cloud and agent engineering** | EC2, S3, IAM, infrastructure as code, bounded jobs, cleanup, task ownership, durable artifacts, independent checks | Runs training remotely and prevents long tasks from depending on an agent remembering everything |

**Three topics deserve extra depth.**

**Decision boundaries and sensitivity.**
A tiny error in learned potential can change escape into capture near the boundary between those outcomes.
Study unstable equilibria, separatrices, numerical conditioning, and safety margins.
This explains original experiment’s central result.

**Model predictive control.**
Predict several possible futures, choose a plan, execute only its first action, then observe again.
This explains current pilot more directly than starting with diffusion mathematics.

**Evidence and guarantees.**
Training loss measures fit.
Flight evaluation measures behavior.
An exact certificate establishes a specific mathematical claim.
Each answers a different question.
Powered pilot uses numerical ranking; exact certificate belongs to earlier unpowered experiment.

For practical understanding, work through these exercises:

1. **Simulate one unpowered orbit.**
   Plot radius over proper time.
   Check energy and angular momentum conservation.
2. **Add one engine burn.**
   Observe changes in trajectory, energy, and remaining fuel.
3. **Build a simple planner.**
   Try fixed burn sequences, score them, execute first command, repeat.
4. **Inspect autoencoder reconstruction.**
   Compare original and reconstructed commands, separating burns from coasting.
5. **Generate several diffusion plans.**
   Compare plausible-looking plans with their actual simulated outcomes.
6. **Challenge the checker.**
   Change a certificate coefficient and confirm rejection.
7. **Trace one light ray.**
   Follow it until disk intersection, distant escape, or horizon cutoff.
8. **Reproduce walking bug.**
   Compare movement using full camera rotation with movement restricted to horizontal heading.

Useful entry points in your project:

- [Powered physics](../pilot_physics.py)
- [Planning and feedback control](../pilot_control.py)
- [Autoencoder, transformer, and diffusion inference](../pilot_model.py)
- [Exact certificate checker](../verify_certificate.py)
- [3D rendering and movement](../dashboard/cockpit-3d.js)
- [Full experiment explanation](pilot-article.md)

**Start with simulation and simple planning.**
Once that loop makes sense, autoencoders and diffusion become concrete: they supply candidate plans to an already understandable control system.
