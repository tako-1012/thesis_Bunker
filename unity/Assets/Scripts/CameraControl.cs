using UnityEngine;

/// <summary>
/// Simple orbit/zoom camera control for scene inspection.
/// Left-drag to rotate, scroll to zoom, right-drag to pan.
/// </summary>
public class CameraControl : MonoBehaviour
{
    public Transform target;
    public float distance = 10f;
    public float zoomSpeed = 2f;
    public float rotateSpeed = 4f;
    public float panSpeed = 0.5f;

    Vector3 lastPos;

    void Start()
    {
        if (target == null) target = new GameObject("CameraTarget").transform;
        transform.position = target.position - transform.forward * distance;
    }

    void LateUpdate()
    {
        if (Input.GetMouseButtonDown(0) || Input.GetMouseButtonDown(1)) lastPos = Input.mousePosition;

        if (Input.GetMouseButton(0))
        {
            Vector3 delta = Input.mousePosition - lastPos;
            transform.RotateAround(target.position, Vector3.up, delta.x * rotateSpeed * Time.deltaTime);
            transform.RotateAround(target.position, transform.right, -delta.y * rotateSpeed * Time.deltaTime);
            lastPos = Input.mousePosition;
        }

        if (Input.GetMouseButton(1))
        {
            Vector3 delta = Input.mousePosition - lastPos;
            transform.Translate(-delta.x * panSpeed * Time.deltaTime, -delta.y * panSpeed * Time.deltaTime, 0);
            lastPos = Input.mousePosition;
        }

        float scroll = Input.GetAxis("Mouse ScrollWheel");
        if (Mathf.Abs(scroll) > 1e-4f)
        {
            transform.position += transform.forward * scroll * zoomSpeed;
        }
    }
}
