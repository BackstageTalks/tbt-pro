Place the six generated WebP files in this exact directory:
blinq/web/assets/avatars/

free_a.webp
free_b.webp
pro_a.webp
pro_b.webp
pro_plus_a.webp
pro_plus_b.webp

Recommended: 1024 x 1024 px, square, WebP, dark or transparent background
Access rules implemented in render.py:
FREE: free_a, free_b
PRO: free_a, free_b, pro_a, pro_b
PRO+: all six avatars
Locked avatar click opens the existing Upgrade modal
Selected avatar is saved in Supabase user_metadata.avatar_code
