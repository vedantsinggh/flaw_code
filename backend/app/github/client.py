import logging
import os
import base64
import httpx
from typing import Dict, Any, List
from app.config import settings

logger = logging.getLogger("forgeos.github")

class GitHubClient:
    def __init__(self):
        pass

    async def create_branch(self, branch_name: str) -> bool:
        """
        Creates a git branch.
        """
        logger.info(f"[GITHUB] Creating branch '{branch_name}'")
        if not settings.GITHUB_TOKEN:
            raise RuntimeError("GITHUB_TOKEN is not configured. Real GitHub operations are required.")
            
        try:
            owner_repo = settings.GITHUB_REPOSITORY # e.g. "user/repo"
            headers = {
                "Authorization": f"token {settings.GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3+json"
            }
            async with httpx.AsyncClient(timeout=60.0) as client:
                # 1. Get SHA of main branch
                ref_url = f"https://api.github.com/repos/{owner_repo}/git/ref/heads/main"
                r = await client.get(ref_url, headers=headers)
                if r.status_code != 200:
                    raise RuntimeError(f"Failed to fetch main branch ref: {r.text}")
                sha = r.json()["object"]["sha"]
                
                # 2. Create new branch ref
                create_ref_url = f"https://api.github.com/repos/{owner_repo}/git/refs"
                payload = {
                    "ref": f"refs/heads/{branch_name}",
                    "sha": sha
                }
                r2 = await client.post(create_ref_url, headers=headers, json=payload)
                if r2.status_code not in (200, 201):
                    if "already exists" in r2.text:
                        logger.info(f"Branch '{branch_name}' already exists.")
                        return True
                    raise RuntimeError(f"Failed to create branch: {r2.text}")
                return True
        except Exception as e:
            logger.error(f"Failed to create branch remotely: {str(e)}")
            raise

    async def create_commit(self, branch: str, commit_message: str, files_changed: List[str]) -> bool:
        """
        Creates a Git commit.
        """
        logger.info(f"[GITHUB] Creating commit on branch '{branch}' with msg '{commit_message}'")
        logger.info(f"[GITHUB] Files affected: {files_changed}")
        
        if not settings.GITHUB_TOKEN:
            raise RuntimeError("GITHUB_TOKEN is not configured. Real GitHub operations are required.")
            
        try:
            owner_repo = settings.GITHUB_REPOSITORY
            headers = {
                "Authorization": f"token {settings.GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3+json"
            }
            async with httpx.AsyncClient(timeout=60.0) as client:
                for file_path in files_changed:
                    rel_path = os.path.relpath(file_path, "/home/mirage/Projects/forge2")
                    if rel_path.startswith(".."):
                        rel_path = os.path.basename(file_path)
                    
                    with open(file_path, "rb") as f:
                        content_bytes = f.read()
                    content_b64 = base64.b64encode(content_bytes).decode("utf-8")
                    
                    # Try to get the file to see if it exists (to get its sha)
                    file_url = f"https://api.github.com/repos/{owner_repo}/contents/{rel_path}?ref={branch}"
                    r = await client.get(file_url, headers=headers)
                    sha = None
                    if r.status_code == 200:
                        sha = r.json()["sha"]
                    
                    # Create or update file content
                    payload = {
                        "message": commit_message,
                        "content": content_b64,
                        "branch": branch
                    }
                    if sha:
                        payload["sha"] = sha
                        
                    put_url = f"https://api.github.com/repos/{owner_repo}/contents/{rel_path}"
                    r2 = await client.put(put_url, headers=headers, json=payload)
                    if r2.status_code not in (200, 201):
                        raise RuntimeError(f"Failed to commit file {rel_path}: {r2.text}")
                return True
        except Exception as e:
            logger.error(f"Failed to create commit remotely: {str(e)}")
            raise

    async def create_pull_request(self, title: str, body: str, head_branch: str, base_branch: str = "main") -> Dict[str, Any]:
        """
        Submits a pull request.
        """
        logger.info(f"[GITHUB] Creating PR: '{title}' from '{head_branch}' into '{base_branch}'")
        
        if not settings.GITHUB_TOKEN:
            raise RuntimeError("GITHUB_TOKEN is not configured. Real GitHub operations are required.")
            
        try:
            owner_repo = settings.GITHUB_REPOSITORY
            headers = {
                "Authorization": f"token {settings.GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3+json"
            }
            async with httpx.AsyncClient(timeout=60.0) as client:
                url = f"https://api.github.com/repos/{owner_repo}/pulls"
                payload = {
                    "title": title,
                    "body": body,
                    "head": head_branch,
                    "base": base_branch
                }
                r = await client.post(url, headers=headers, json=payload)
                if r.status_code not in (200, 201):
                    # Check if PR already exists
                    if "A pull request already exists" in r.text:
                        list_url = f"https://api.github.com/repos/{owner_repo}/pulls?head={owner_repo.split('/')[0]}:{head_branch}&base={base_branch}"
                        r_list = await client.get(list_url, headers=headers)
                        if r_list.status_code == 200 and r_list.json():
                            pr_info = r_list.json()[0]
                            return {
                                "id": pr_info["number"],
                                "url": pr_info["html_url"],
                                "status": "Open",
                                "title": pr_info["title"]
                            }
                    raise RuntimeError(f"Failed to create pull request: {r.text}")
                pr_info = r.json()
                return {
                    "id": pr_info["number"],
                    "url": pr_info["html_url"],
                    "status": "Open",
                    "title": pr_info["title"]
                }
        except Exception as e:
            logger.error(f"Failed to create pull request: {str(e)}")
            raise

    async def create_issue(self, title: str, body: str) -> Dict[str, Any]:
        """
        Creates a repository bug report or task issue.
        """
        logger.info(f"[GITHUB] Creating issue: '{title}'")
        
        if not settings.GITHUB_TOKEN:
            raise RuntimeError("GITHUB_TOKEN is not configured. Real GitHub operations are required.")
            
        try:
            owner_repo = settings.GITHUB_REPOSITORY
            headers = {
                "Authorization": f"token {settings.GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3+json"
            }
            async with httpx.AsyncClient(timeout=60.0) as client:
                url = f"https://api.github.com/repos/{owner_repo}/issues"
                payload = {
                    "title": title,
                    "body": body
                }
                r = await client.post(url, headers=headers, json=payload)
                if r.status_code not in (200, 201):
                    raise RuntimeError(f"Failed to create issue: {r.text}")
                issue_info = r.json()
                return {
                    "id": issue_info["number"],
                    "url": issue_info["html_url"],
                    "title": issue_info["title"]
                }
        except Exception as e:
            logger.error(f"Failed to create issue: {str(e)}")
            raise

github_client = GitHubClient()
