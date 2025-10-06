using UnityEngine;
using System.Collections.Generic;

public class PathCreator : MonoBehaviour
{
    [Header("Path Settings")]
    public float pathWidth = 3f;
    public int pathPoints = 20;
    public float pathRadius = 20f;
    public Material pathMaterial;
    
    [Header("Waypoint Settings")]
    public bool createWaypoints = true;
    public GameObject waypointPrefab;
    
    private List<Vector3> pathPositions = new List<Vector3>();
    
    void Start()
    {
        CreateCircularPath();
    }
    
    void CreateCircularPath()
    {
        // Clear existing path
        ClearPath();
        
        // Generate circular path points
        pathPositions.Clear();
        for (int i = 0; i < pathPoints; i++)
        {
            float angle = (float)i / pathPoints * 2 * Mathf.PI;
            Vector3 position = new Vector3(
                Mathf.Cos(angle) * pathRadius,
                0.1f, // Slightly above ground
                Mathf.Sin(angle) * pathRadius
            );
            pathPositions.Add(position);
        }
        
        // Create path segments
        for (int i = 0; i < pathPositions.Count; i++)
        {
            CreatePathSegment(i);
        }
        
        // Create waypoints if enabled
        if (createWaypoints)
        {
            CreateWaypoints();
        }
        
        Debug.Log($"Created circular path with {pathPoints} segments");
    }
    
    void CreatePathSegment(int index)
    {
        Vector3 currentPos = pathPositions[index];
        Vector3 nextPos = pathPositions[(index + 1) % pathPositions.Count];
        
        // Calculate segment properties
        Vector3 direction = (nextPos - currentPos).normalized;
        float distance = Vector3.Distance(currentPos, nextPos);
        Vector3 midPoint = (currentPos + nextPos) / 2;
        
        // Create path segment
        GameObject pathSegment = GameObject.CreatePrimitive(PrimitiveType.Cube);
        pathSegment.transform.position = midPoint;
        pathSegment.transform.localScale = new Vector3(pathWidth, 0.1f, distance);
        pathSegment.transform.LookAt(midPoint + direction);
        
        // Apply material
        Renderer renderer = pathSegment.GetComponent<Renderer>();
        if (pathMaterial != null)
        {
            renderer.material = pathMaterial;
        }
        else
        {
            renderer.material.color = new Color(0.4f, 0.4f, 0.4f); // Dark gray
        }
        
        pathSegment.tag = "Path";
        pathSegment.name = $"PathSegment_{index}";
        pathSegment.transform.SetParent(this.transform);
    }
    
    void CreateWaypoints()
    {
        // Create waypoints at every 4th path point
        for (int i = 0; i < pathPositions.Count; i += 4)
        {
            Vector3 waypointPos = pathPositions[i] + Vector3.up * 2f;
            
            GameObject waypoint;
            if (waypointPrefab != null)
            {
                waypoint = Instantiate(waypointPrefab, waypointPos, Quaternion.identity);
            }
            else
            {
                waypoint = GameObject.CreatePrimitive(PrimitiveType.Sphere);
                waypoint.transform.position = waypointPos;
                waypoint.transform.localScale = Vector3.one * 0.5f;
                
                Renderer renderer = waypoint.GetComponent<Renderer>();
                renderer.material.color = Color.green;
            }
            
            waypoint.tag = "Waypoint";
            waypoint.name = $"Waypoint_{i/4}";
            waypoint.transform.SetParent(this.transform);
        }
    }
    
    void ClearPath()
    {
        // Clear existing path segments
        for (int i = transform.childCount - 1; i >= 0; i--)
        {
            DestroyImmediate(transform.GetChild(i).gameObject);
        }
    }
    
    [ContextMenu("Recreate Path")]
    void RecreatePath()
    {
        CreateCircularPath();
    }
    
    [ContextMenu("Create Oval Path")]
    void CreateOvalPath()
    {
        pathPositions.Clear();
        
        // Create oval shape
        for (int i = 0; i < pathPoints; i++)
        {
            float angle = (float)i / pathPoints * 2 * Mathf.PI;
            Vector3 position = new Vector3(
                Mathf.Cos(angle) * pathRadius * 1.5f, // Elongated X
                0.1f,
                Mathf.Sin(angle) * pathRadius
            );
            pathPositions.Add(position);
        }
        
        ClearPath();
        
        for (int i = 0; i < pathPositions.Count; i++)
        {
            CreatePathSegment(i);
        }
        
        if (createWaypoints)
        {
            CreateWaypoints();
        }
        
        Debug.Log("Created oval path");
    }
}