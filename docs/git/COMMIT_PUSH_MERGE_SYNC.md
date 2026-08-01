# Commit, Push, Merge, Sync

This is the standard workflow when the user says:

```text
commit, push, merge, and sync
```

Its intended result is:

```text
finish the current working branch
land it on main with a fast-forward
push main
verify local and remote agreement
return to the working branch
```

## Default flow

Assume the current branch is the working branch.

1. Inspect the branch and worktree.

   ```bash
   git status --short --branch
   git branch --show-current
   ```

2. Review and verify changes before staging.

   ```bash
   git diff --stat
   git diff --check
   ```

3. Fetch and compare local and remote history. Do not assume the branch base.

   ```bash
   git fetch origin
   git log --oneline --decorate --graph --max-count=20 --all
   git rev-list --left-right --count origin/main...main
   git rev-list --left-right --count main...<working-branch>
   ```

4. Stage only files belonging to the task, then commit them with a concise message.

   ```bash
   git add <intended-files>
   git commit -m "short commit message"
   ```

   Use `git add -A` only when the entire worktree is confirmed to be in scope.

5. Push the working branch.

   ```bash
   git push -u origin <working-branch>
   ```

6. Switch to `main` and update it without rewriting history.

   ```bash
   git switch main
   git pull --ff-only origin main
   ```

7. Fast-forward `main` to the working branch.

   ```bash
   git merge --ff-only <working-branch>
   ```

   If fast-forward is impossible, stop and inspect the divergence. Do not create a
   surprise merge commit, rebase published work, reset, or force-push.

8. Push `main`, fetch, and prove synchronization.

   ```bash
   git push origin main
   git fetch origin
   git status --short --branch
   git rev-list --left-right --count origin/main...main
   ```

   A synchronized `main` reports `0 0`.

9. If remote `main` moved during the workflow, use `git pull --ff-only origin main`
   and inspect any non-fast-forward result before continuing.

10. Return to the original working branch and verify both refs.

    ```bash
    git switch <working-branch>
    git status --short --branch
    git rev-list --left-right --count origin/main...main
    git rev-list --left-right --count origin/<working-branch>...<working-branch>
    ```

## Empty-repository bootstrap

An empty GitHub repository has no `origin/main` to update. For its first publication:

1. Create and commit the intended initial state on a named working branch.
2. Create local `main` at that exact commit and push `main` first so GitHub selects it
   as the repository's default branch.
3. Return to and push the working branch.
4. Verify GitHub's default branch is `main` and both local/remote pairs report `0 0`.

The first publication therefore has no divergent history to merge; the working branch
and `main` intentionally start at the same commit.

If the working branch was pushed first, GitHub may select it as the default. Change the
repository's default-branch setting to `main` before declaring synchronization complete.
The repository's `Default Branch Contract` workflow checks this invariant on every push
to `main` and once each day so a later administrative change becomes visible.

## Multi-repository rules

- Treat Nexus, Forge, and Parallax as independent repositories.
- Complete and push a product change before updating its umbrella submodule pin.
- Never stage unrelated product changes from the umbrella repository.
- Verify each affected product's `main` independently before publishing umbrella pins.
- Do not delete source branches unless the user explicitly asks.
- Leave every checkout on its working branch after synchronization.

## Finished state

```text
main == origin/main
working branch == origin/working branch
worktree contains no uncommitted task files
checkout is back on the working branch
```
