# --- Shader Code ---
vertex_shader = """
    uniform mat4 u_modelViewProjectionMatrix;
    uniform mat4 u_sceneCameraViewMatrix;
    uniform mat4 u_modelMatrix;

    in vec3 pos;
    in vec3 normal;
    out float v_scene_cam_depth;
    out vec3 v_normal;

    void main()
    {
        gl_Position = u_modelViewProjectionMatrix * vec4(pos, 1.0);

        vec4 world_pos = u_modelMatrix * vec4(pos, 1.0);
        vec4 scene_cam_view_pos = u_sceneCameraViewMatrix * world_pos;
        v_scene_cam_depth = -scene_cam_view_pos.z;

        v_normal = (u_modelMatrix * vec4(normal, 0.0)).xyz;
    }
"""

fragment_shader = """
    uniform vec4 u_in_focus_color;
    uniform vec4 u_near_color;
    uniform vec4 u_far_color;
    uniform float u_dof_near_plane;
    uniform float u_dof_far_plane;
    uniform float u_focus_distance;
    uniform float u_frag_depth_offset;
    uniform vec4 u_far_gradient_color;
    uniform vec3 u_light_direction;
    uniform float u_ambient_factor;
    uniform vec4 u_focus_plane_color;
    uniform float u_focus_plane_tolerance;
    uniform bool u_show_focal_plane;
    uniform bool u_show_dof_limits;
    uniform bool u_show_depth_of_field;

    in float v_scene_cam_depth;
    in vec3 v_normal;
    out vec4 fragColor;

    void main()
    {
        gl_FragDepth = gl_FragCoord.z - u_frag_depth_offset;

        // Laser effect for focus plane
        if (u_show_focal_plane && abs(v_scene_cam_depth - u_focus_distance) < u_focus_plane_tolerance) {
            fragColor = u_focus_plane_color;
            return;
        }

        // Laser effect for DoF limits
        if (u_show_dof_limits) {
            if (abs(v_scene_cam_depth - u_dof_near_plane) < u_focus_plane_tolerance) {
                fragColor = u_near_color;
                return;
            }
            // Only draw the far limit if it's not at infinity
            if (u_dof_far_plane < 1.0e37 && abs(v_scene_cam_depth - u_dof_far_plane) < u_focus_plane_tolerance) {
                fragColor = u_far_color;
                return;
            }
        }

        vec3 normalized_normal = normalize(v_normal);
        float light_factor = max(dot(normalized_normal, normalize(u_light_direction)), 0.0);

        vec4 base_color;
        if (u_show_depth_of_field) {
            if (v_scene_cam_depth >= u_dof_near_plane && v_scene_cam_depth <= u_dof_far_plane)
            {
                base_color = u_in_focus_color;
            }
            else if (v_scene_cam_depth > u_dof_far_plane) // Far field (background)
            {
                // Simplified and more robust gradient calculation
                // We interpolate directly based on the distance between the far DoF plane and the hyperfocal distance.
                // This avoids the numerical instability of the CoC calculations at large distances.

                float gradient_start = u_dof_far_plane;
                float gradient_end = u_dof_far_plane * 2.3 + u_focus_distance / 2;

                // If the far plane is at infinity or beyond the hyperfocal distance, just use the far color.
                if (gradient_start >= gradient_end) {
                    base_color = u_far_color;
                } else {
                    // Calculate 't' as the normalized position of the fragment within the gradient range.
                    float t = clamp((v_scene_cam_depth - gradient_start) / (gradient_end - gradient_start), 0.0, 1.0);

                    // Apply the same multi-stop gradient logic as before.
                    if (t < 0.8) {
                        // Remap t from [0, 0.8] to [0, 1] for the first gradient segment
                        float t_segment1 = t / 0.8;
                        base_color = mix(u_in_focus_color, u_far_gradient_color, t_segment1);
                    } else {
                        // Remap t from [0.8, 1.0] to [0, 1] for the second gradient segment
                        float t_segment2 = (t - 0.8) / 0.2;
                        base_color = mix(u_far_gradient_color, u_far_color, t_segment2);
                    }
                }
            }
            else // Near field (foreground)
            {
                // Simplified and robust gradient from the near DoF plane to the camera.
                float gradient_start = 0.0; // Camera position
                float gradient_end = u_dof_near_plane;

                // Avoid division by zero if the near plane is at the camera.
                if (gradient_end <= 0.0) {
                    base_color = u_near_color;
                } else {
                    // Calculate 't' as the normalized position of the fragment within the gradient range.
                    // t = 0 at the camera (full near color), t = 1 at the near plane (in-focus color).
                    float t = clamp(v_scene_cam_depth / gradient_end, 0.0, 1.0);

                    // We mix from near_color to in_focus_color as depth increases.
                    // The t*t gives a more gradual falloff.
                    base_color = mix(u_near_color, u_in_focus_color, t * t);
                }
            }
        } else {
            base_color = u_in_focus_color; // Default to in-focus color if gradients are off
        }

        fragColor = vec4(base_color.rgb * (light_factor + u_ambient_factor), base_color.a);
    }
"""
