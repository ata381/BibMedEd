# Contributing to BibMedEd

Thanks for your interest in improving **BibMedEd**! This project is designed to be friendly to first-time open-source contributors and domain experts in medical education.

## High-impact ways to contribute

1. **Add a new source adapter**
   - Implement a new adapter in `bibmeded/backend/app/adapters/`.
   - Follow the adapter docs: <https://ata381.github.io/BibMedEd/adapters/>.
2. **Improve analysis quality or visualizations**
   - Add metrics, improve network analysis behavior, or enhance dashboard UX.
3. **Strengthen docs and examples**
   - Clarify setup, troubleshooting, and methodology reproducibility.
4. **Report bugs and suggest features**
   - Open an issue with steps to reproduce and expected behavior.

## Development setup

```bash
git clone https://github.com/ata381/BibMedEd
cd BibMedEd/bibmeded
docker compose up --build
```

Then open:
- Frontend: <http://localhost:3000>
- Backend API docs: <http://localhost:8000/docs>

## Contribution workflow

1. Fork the repository.
2. Create a branch: `git checkout -b feat/short-description`.
3. Make focused, atomic commits.
4. Run local checks relevant to your changes.
5. Open a pull request with:
   - Problem statement
   - What changed
   - Screenshots (for UI changes)
   - Any migration or compatibility notes

## Pull request checklist

- [ ] I linked the related issue (if one exists).
- [ ] I kept the change focused and documented non-obvious decisions.
- [ ] I updated docs when behavior or configuration changed.
- [ ] I included screenshots for frontend/UI changes.
- [ ] I verified the app runs via Docker Compose.

## Style and scope guidelines

- Keep PRs small enough for fast review.
- Prefer clear naming and explicit data contracts.
- Preserve reproducibility features (methodology logging, exports).
- For adapter contributions, ensure mapped `external_ids` are stable.

## Need help?

If you are unsure where to start, open an issue titled **"Good first issue request"** and describe your background (engineering, statistics, med-ed research, etc.). We'll help you find a useful task.
